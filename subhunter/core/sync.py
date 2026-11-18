"""Re-time a downloaded subtitle to the video it belongs to.

Releases of the same episode often differ by a constant offset (different intro
cut, encoder delay...) or by a framerate conversion (PAL 25 fps vs 23.976 fps).

1. If the video already carries a text track in any language, its line timings
   are the reference: every (reference, downloaded) pair of line starts votes
   for an offset, and the most voted offset/framerate wins. Fast and exact.
2. Otherwise (or if no track agrees) alass aligns the subtitle against the
   audio track via speech detection, which takes a few seconds per episode.
"""
import bisect
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

import pysubs2

logger = logging.getLogger(__name__)

TEXT_CODECS = {"ass", "ssa", "subrip", "srt", "webvtt", "mov_text"}
MIN_SHIFT = 0.25      # seconds; below this it's not noticeable
MAX_SHIFT = 120.0
MIN_ALIGNED = 0.35    # share of lines that must land on a reference line
TOLERANCE = 0.3
BIN = 0.1             # vote resolution in seconds
# Speed ratios between common framerates (subtitle fps / video fps)
SCALES = (1.0, 25 / 23.976, 23.976 / 25, 24 / 23.976, 23.976 / 24, 25 / 24, 24 / 25)
SCALE_MARGIN = 0.1    # a framerate change must beat 1.0 by this much to be used
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_SUB_FORMATS = ("ass", "ssa", "srt", "vtt")

SYNCED, IN_SYNC = "synced", "in_sync"


def _run(args, timeout=120):
    return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)


def _tool(name):
    """Bundled binary (PyInstaller or repo bin/) first, then PATH."""
    exe = name + (".exe" if sys.platform == "win32" else "")
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    bundled = os.path.join(base, "bin", exe)
    return bundled if os.path.isfile(bundled) else shutil.which(name)


def _reference_tracks(video_path, ffprobe):
    r = _run([ffprobe, "-v", "error", "-select_streams", "s",
              "-show_entries", "stream=index,codec_name", "-of", "json", video_path])
    if r.returncode != 0:
        return []
    streams = json.loads(r.stdout or b"{}").get("streams", [])
    return [s["index"] for s in streams if s.get("codec_name") in TEXT_CODECS]


def _starts(subs):
    return sorted(e.start / 1000 for e in subs if not e.is_comment and e.plaintext.strip())


def _aligned(reference, candidate, scale, offset):
    """Share of candidate lines that land within TOLERANCE of a reference line."""
    hits = 0
    for t in candidate:
        t = t * scale + offset
        i = bisect.bisect_left(reference, t)
        if any(0 <= j < len(reference) and abs(reference[j] - t) < TOLERANCE for j in (i - 1, i)):
            hits += 1
    return hits / len(candidate)


def _fit(reference, candidate, scale):
    """Most voted offset for this scale, refined to the median of its votes."""
    votes = Counter()
    pairs = []
    for t in candidate:
        t *= scale
        lo = bisect.bisect_left(reference, t - MAX_SHIFT)
        hi = bisect.bisect_right(reference, t + MAX_SHIFT)
        for r in reference[lo:hi]:
            votes[round((r - t) / BIN)] += 1
            pairs.append(r - t)
    if not votes:
        return None
    width = round(TOLERANCE / BIN)
    peak = max(votes, key=lambda b: sum(votes.get(b + k, 0) for k in range(-width, width + 1)))
    near = sorted(d for d in pairs if abs(d - peak * BIN) < TOLERANCE)
    offset = near[len(near) // 2]
    return offset, _aligned(reference, candidate, scale, offset)


def _best_fit(reference, candidate):
    """(scale, offset, aligned) that best maps candidate onto reference."""
    best = None
    for scale in SCALES:
        fit = _fit(reference, candidate, scale)
        if not fit:
            continue
        margin = 0 if scale == 1.0 else SCALE_MARGIN
        if best is None or fit[1] > best[2] + margin:
            best = (scale, *fit)
    return best


def _retime(subs, scale, offset):
    for e in subs:
        e.start = max(0, round(e.start * scale + offset * 1000))
        e.end = max(e.start, round(e.end * scale + offset * 1000))


def _sync_embedded(video_path, subs, tracks, ffmpeg):
    """Re-time subs in place against an embedded text track.
    Returns SYNCED, IN_SYNC, or None when no track is a usable reference."""
    candidate = _starts(subs)
    if len(candidate) < 20:
        return None

    best = None
    with tempfile.TemporaryDirectory() as tmp:
        for idx in tracks:
            out = os.path.join(tmp, f"ref{idx}.ass")
            if _run([ffmpeg, "-v", "error", "-y", "-i", video_path,
                     "-map", f"0:{idx}", out]).returncode != 0:
                continue
            reference = _starts(pysubs2.load(out))
            # Signs-only tracks are too sparse to be a reference
            if len(reference) < len(candidate) * 0.5:
                continue
            fit = _best_fit(reference, candidate)
            if fit and (best is None or fit[2] > best[2]):
                best = fit

    name = os.path.basename(video_path)
    if not best or best[2] < MIN_ALIGNED:
        logger.info("No embedded track matches %s (best fit: %s)", name, best)
        return None
    scale, offset, aligned = best
    if scale == 1.0 and abs(offset) < MIN_SHIFT:
        logger.info("%s already in sync (%.0f%% of lines agree)", name, aligned * 100)
        return IN_SYNC
    _retime(subs, scale, offset)
    logger.info("Synced %s to embedded track: x%.4f %+.2fs (%.0f%% of lines agree)",
                name, scale, offset, aligned * 100)
    return SYNCED


def _sync_audio(video_path, subs, fmt, ffmpeg, ffprobe):
    """Re-time subs against the audio with alass. Returns new subs or None."""
    alass = _tool("alass-cli")
    if not alass:
        logger.info("alass not available, skipping audio sync")
        return None
    ext = fmt if fmt in ("ass", "ssa", "srt") else "srt"
    env = dict(os.environ, ALASS_FFMPEG_PATH=ffmpeg, ALASS_FFPROBE_PATH=ffprobe)
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, f"in.{ext}"), os.path.join(tmp, f"out.{ext}")
        subs.save(src, format_=ext)
        # --no-split: a single offset + framerate fit; split mode is slower and
        # misplaces lines when the translation's timing differs from the audio
        r = subprocess.run([alass, "--no-split", video_path, src, dst], capture_output=True,
                           timeout=900, creationflags=_NO_WINDOW, env=env)
        if r.returncode != 0 or not os.path.exists(dst):
            logger.warning("alass failed for %s: %s", os.path.basename(video_path),
                           r.stderr.decode(errors="replace")[-300:])
            return None
        synced = pysubs2.load(dst)
    logger.info("Synced %s to audio with alass", os.path.basename(video_path))
    return synced


def _decode(content):
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", "replace")  # older Spanish/European subs


def resync(video_path, content, fmt, use_audio=True):
    """Re-time subtitle bytes to the video.
    Returns (status, new_content): (SYNCED, bytes), (IN_SYNC, None) or (None, None)."""
    ffmpeg, ffprobe = _tool("ffmpeg"), _tool("ffprobe")
    if not ffmpeg or not ffprobe:
        return None, None
    try:
        subs = pysubs2.SSAFile.from_string(_decode(content))
        tracks = _reference_tracks(video_path, ffprobe)
        result = _sync_embedded(video_path, subs, tracks, ffmpeg) if tracks else None
        if result == IN_SYNC:
            return IN_SYNC, None
        if result is None:
            if not use_audio:
                return None, None
            subs = _sync_audio(video_path, subs, fmt, ffmpeg, ffprobe)
            if subs is None:
                return None, None
        return SYNCED, subs.to_string(fmt if fmt in _SUB_FORMATS else "srt").encode("utf-8")
    except Exception as e:
        logger.warning("Sync failed for %s: %s", os.path.basename(video_path), e)
        return None, None


def sync_subtitle(video_path, content, fmt, use_audio=True):
    """Return content re-timed to the video, or None if not needed/possible."""
    return resync(video_path, content, fmt, use_audio)[1]
