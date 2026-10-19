"""Shift a downloaded subtitle to match a text subtitle track embedded in the video.

Releases of the same episode often differ by a constant offset (different intro
cut, encoder delay...). When the video already carries a text track in any
language, its line timings are a good reference: we take the median distance
from each downloaded line to the nearest reference line and shift by it.
"""
import bisect
import json
import logging
import os
import shutil
import subprocess
import tempfile

import pysubs2

logger = logging.getLogger(__name__)

TEXT_CODECS = {"ass", "ssa", "subrip", "srt", "webvtt", "mov_text"}
MIN_SHIFT = 0.25      # seconds; below this it's not noticeable
MAX_SHIFT = 120.0
MIN_ALIGNED = 0.5     # share of lines that must agree with the offset
TOLERANCE = 0.3
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(args):
    return subprocess.run(args, capture_output=True, timeout=120, creationflags=_NO_WINDOW)


def _reference_tracks(video_path, ffprobe):
    r = _run([ffprobe, "-v", "error", "-select_streams", "s",
              "-show_entries", "stream=index,codec_name", "-of", "json", video_path])
    if r.returncode != 0:
        return []
    streams = json.loads(r.stdout or b"{}").get("streams", [])
    return [s["index"] for s in streams if s.get("codec_name") in TEXT_CODECS]


def _starts(subs):
    return sorted(e.start / 1000 for e in subs if not e.is_comment and e.plaintext.strip())


def _offset(reference, candidate):
    diffs = []
    for t in candidate:
        i = bisect.bisect_left(reference, t)
        near = [reference[j] for j in (i - 1, i) if 0 <= j < len(reference)]
        if near:
            diffs.append(min(near, key=lambda x: abs(x - t)) - t)
    if not diffs:
        return None, 0.0
    diffs.sort()
    median = diffs[len(diffs) // 2]
    aligned = sum(abs(d - median) < TOLERANCE for d in diffs) / len(diffs)
    return median, aligned


def sync_to_embedded(video_path, content, fmt):
    """Return content shifted to the video's embedded track, or None if not needed/possible."""
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        return None
    try:
        tracks = _reference_tracks(video_path, ffprobe)
        if not tracks:
            return None
        subs = pysubs2.SSAFile.from_string(content.decode("utf-8-sig", "replace"))
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
                offset, aligned = _offset(reference, candidate)
                if offset is not None and (best is None or aligned > best[1]):
                    best = (offset, aligned)

        if not best:
            return None
        offset, aligned = best
        if aligned < MIN_ALIGNED or not MIN_SHIFT <= abs(offset) <= MAX_SHIFT:
            logger.debug("No sync for %s: offset %.2fs, aligned %.0f%%",
                         os.path.basename(video_path), offset, aligned * 100)
            return None

        subs.shift(s=offset)
        logger.info("Synced %s by %+.2fs (%.0f%% of lines agree)",
                    os.path.basename(video_path), offset, aligned * 100)
        return subs.to_string(fmt if fmt in ("ass", "ssa", "srt", "vtt") else "srt").encode("utf-8")
    except Exception as e:
        logger.warning("Sync failed for %s: %s", os.path.basename(video_path), e)
        return None
