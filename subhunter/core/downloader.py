import os
import threading
import time
import traceback

import subliminal_patch  # noqa: F401  (registers Bazarr's providers)
from subliminal.video import Episode
from subliminal_patch.core import SZAsyncProviderPool, scan_video
from subliminal_patch.score import MAX_SCORES, compute_score
from subzero.language import Language

from .anime import refine_anime
from .logger import log
from .metadata import fix_country_title, refine_ids
from .providers import register_custom_providers
from .sync import sync_to_embedded

register_custom_providers()

# subliminal_patch caches provider tokens/lookups in this region
try:
    from subliminal.cache import region
    region.configure("dogpile.cache.memory")
except Exception:
    pass  # Already configured

# Regional variants some providers report separately (e.g. Latin American Spanish)
LANGUAGE_VARIANTS = {
    "spa": [("spa", "MX"), ("spa", "ES")],
    "por": [("por", "BR")],
}

SUBTITLE_EXTENSIONS = {"ass": ".ass", "ssa": ".ssa", "vtt": ".vtt"}


class SubtitleDownloader:
    """Handles subtitle search and download in a background thread."""

    def __init__(self, lang_codes=None, auto_rename=True,
                 providers=None, provider_configs=None, auto_sync=True):
        if lang_codes is None:
            lang_codes = ["spa"]
        self.languages = set()
        for code in lang_codes:
            self.languages.add(Language(code))
            for alpha3, country in LANGUAGE_VARIANTS.get(code, []):
                self.languages.add(Language(alpha3, country))
        self.lang_codes = list(lang_codes)
        self.auto_rename = auto_rename
        self.auto_sync = auto_sync
        self.providers = providers or []
        self.provider_configs = provider_configs or {}
        self._on_progress = None
        self._on_item_status = None
        self._on_complete = None

    def on_progress(self, callback):
        self._on_progress = callback

    def on_item_status(self, callback):
        self._on_item_status = callback

    def on_complete(self, callback):
        self._on_complete = callback

    def download(self, file_paths):
        threading.Thread(target=self._run, args=(file_paths,), daemon=True).start()

    def search(self, file_paths, on_results=None):
        """Search all providers and return results without downloading."""
        threading.Thread(
            target=self._run_search, args=(file_paths, on_results), daemon=True
        ).start()

    def download_selection(self, selections, fallbacks=None):
        """Download specific subtitle objects with fallback alternatives.
        selections: dict filepath -> subtitle_obj
        fallbacks: dict filepath -> list of (sub, score, provider) tuples
        """
        threading.Thread(
            target=self._run_selection, args=(selections, fallbacks), daemon=True
        ).start()

    def download_alternative(self, file_path, skip_index=0):
        """Download an alternative subtitle, skipping the first N results."""
        threading.Thread(
            target=self._run_alternative, args=(file_path, skip_index), daemon=True
        ).start()

    @staticmethod
    def _friendly_error(e):
        msg = str(e).lower()
        if "timeout" in msg or "timed out" in msg:
            return "Timeout de conexion"
        if "403" in msg or "forbidden" in msg:
            return "Proveedor bloqueo acceso"
        if "404" in msg or "not found" in msg:
            return "No encontrado en proveedor"
        if "connection" in msg or "resolve" in msg or "getaddrinfo" in msg:
            return "Sin conexion al proveedor"
        if "rate" in msg or "limit" in msg:
            return "Limite de descargas alcanzado"
        if "ssl" in msg or "certificate" in msg:
            return "Error SSL"
        short = str(e)[:40]
        return short if short else "Error desconocido"

    def _status(self, *args):
        if self._on_item_status:
            self._on_item_status(*args)

    def _new_pool(self):
        pool = None

        def throttled(provider, error, ids=None, language=None):
            # Don't keep hammering a provider that already failed in this batch
            log.warning(f"Provider {provider} disabled for this batch: "
                        f"{type(error).__name__}: {str(error)[:200]}")
            if pool is not None:
                pool.discarded_providers.add(provider)

        pool = SZAsyncProviderPool(
            providers=self.providers,
            provider_configs=self.provider_configs,
            throttle_callback=throttled,
        )
        return pool

    def _scan(self, path):
        video = scan_video(path, hints={}, providers=self.providers)
        fix_country_title(video)
        refine_ids(video)
        refine_anime(video)
        return video

    def _rank(self, video, candidates):
        """Score candidates, dropping ones for a different episode or language."""
        kind = "episode" if isinstance(video, Episode) else "movie"
        max_score = MAX_SCORES[kind]
        scored = []
        for sub in candidates:
            if sub.language not in self.languages:
                continue
            try:
                matches = set(sub.get_matches(video))
            except Exception as e:
                log.debug(f"Matching failed for {sub!r}: {e}")
                continue

            hash_ok = "hash" in matches and sub.hash_verifiable
            if kind == "episode" and not hash_ok \
                    and not {"series", "season", "episode"} <= matches:
                log.debug(f"Skipping {sub!r}: other episode ({sorted(matches)})")
                continue

            score, _ = compute_score(matches, sub, video)
            pct = 100 if hash_ok else min(100, round(score / max_score * 100))
            scored.append((sub, pct, sub.provider_name))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _save_subtitle(self, path, sub):
        fmt = (getattr(sub, "format", None) or "srt").lower()
        ext = SUBTITLE_EXTENSIONS.get(fmt, ".srt")
        suffix = ""
        if not self.auto_rename:
            suffix = f".{sub.language.alpha2}"
        elif len(self.lang_codes) > 1:
            suffix = f".{sub.language.alpha3}"
        out = os.path.splitext(path)[0] + suffix + ext
        content = sub.content
        if self.auto_sync:
            content = sync_to_embedded(path, content, fmt) or content
        with open(out, "wb") as f:
            f.write(content)
        return out

    def _try_download(self, pool, path, attempts):
        """Download the first attempt that works; returns the subtitle or None."""
        fname = os.path.basename(path)
        for sub in attempts:
            try:
                if pool.download_subtitle(sub) and sub.content:
                    out = self._save_subtitle(path, sub)
                    sub.saved_path = out
                    log.info(f"OK: {fname} from {sub.provider_name} -> {os.path.basename(out)}")
                    return sub
            except Exception as e:
                log.debug(f"Provider {sub.provider_name} failed for {fname}: {e}")
        return None

    def _search_one(self, pool, path):
        video = self._scan(path)
        return self._rank(video, pool.list_subtitles(video, self.languages))

    def _run(self, file_paths):
        total = len(file_paths)
        downloaded = failed = 0
        log.info(f"Download batch started: {total} files")

        pool = self._new_pool()
        try:
            for i, path in enumerate(file_paths):
                fname = os.path.basename(path)
                self._status(path, "searching")
                try:
                    ranked = self._search_one(pool, path)
                    sub = self._try_download(pool, path, [s for s, _, _ in ranked])
                    if sub:
                        downloaded += 1
                        self._status(path, "downloaded", sub.provider_name)
                    else:
                        failed += 1
                        log.warning(f"Not found: {fname}")
                        self._status(path, "not_found")
                except Exception as e:
                    failed += 1
                    log.error(f"Error: {fname} — {e}\n{traceback.format_exc()}")
                    self._status(path, "error", self._friendly_error(e))

                if self._on_progress:
                    self._on_progress((i + 1) / total)
        finally:
            pool.terminate()

        if self._on_complete:
            self._on_complete(downloaded, failed)

    def _run_search(self, file_paths, on_results):
        results = {}
        total = len(file_paths)
        log.info(f"Search started: {total} files, providers: {', '.join(self.providers)}")

        pool = self._new_pool()
        try:
            for i, path in enumerate(file_paths):
                fname = os.path.basename(path)
                log.debug(f"Searching: {fname}")
                self._status(path, "searching")
                try:
                    scored = self._search_one(pool, path)
                    results[path] = scored
                    if scored:
                        providers = ", ".join(sorted({s[2] for s in scored}))
                        log.info(f"Found {len(scored)} subs for {fname}: [{providers}]")
                        self._status(path, "found", len(scored))
                    else:
                        log.warning(f"No subs found for {fname}")
                        self._status(path, "not_found")
                except Exception as e:
                    results[path] = []
                    log.error(f"Search error: {fname} — {e}\n{traceback.format_exc()}")
                    self._status(path, "error", self._friendly_error(e))

                if self._on_progress:
                    self._on_progress((i + 1) / total)
        finally:
            pool.terminate()

        if on_results:
            on_results(results)

    def _run_selection(self, selections, fallbacks=None):
        """Download specific subtitle objects chosen by user, with auto-fallback."""
        total = len(selections)
        downloaded = failed = 0
        fallbacks = fallbacks or {}
        log.info(f"Download selection started: {total} files")

        def attempts_for(path, chosen):
            return [chosen] + [s for s, _, _ in fallbacks.get(path, []) if s is not chosen]

        pending = []
        pool = self._new_pool()
        try:
            for i, (path, chosen) in enumerate(selections.items()):
                self._status(path, "searching")
                sub = self._try_download(pool, path, attempts_for(path, chosen))
                if sub:
                    downloaded += 1
                    label = sub.provider_name if sub is chosen else f"{sub.provider_name} (fallback)"
                    self._status(path, "downloaded", label)
                else:
                    pending.append((path, chosen))
                    log.warning(f"First pass failed for {os.path.basename(path)}, will retry")

                if self._on_progress:
                    self._on_progress((i + 1) / total)
                # Small delay between downloads to avoid rate limiting
                time.sleep(0.5)
        finally:
            pool.terminate()

        # Retry failed items with a fresh provider pool
        if pending:
            log.info(f"Retrying {len(pending)} failed downloads with fresh pool")
            time.sleep(2)
            pool = self._new_pool()
            try:
                for path, chosen in pending:
                    self._status(path, "searching")
                    sub = self._try_download(pool, path, attempts_for(path, chosen))
                    if sub:
                        downloaded += 1
                        self._status(path, "downloaded", f"{sub.provider_name} (retry)")
                    else:
                        failed += 1
                        log.error(f"All providers failed for {os.path.basename(path)} (after retry)")
                        self._status(path, "error", "Todos los proveedores fallaron")
                    time.sleep(0.5)
            finally:
                pool.terminate()

        if self._on_complete:
            self._on_complete(downloaded, failed)

    def _run_alternative(self, file_path, skip_index):
        self._status(file_path, "searching")
        pool = self._new_pool()
        try:
            candidates = self._search_one(pool, file_path)
            remaining = [s for s, _, _ in candidates[skip_index:]]
            if not remaining:
                self._status(file_path, "no_more")
                if self._on_complete:
                    self._on_complete(0, 1)
                return

            sub = self._try_download(pool, file_path, remaining)
            if sub:
                # Drop the previous subtitle if it had another extension
                base = os.path.splitext(sub.saved_path)[0]
                for ext in (".srt", ".ass", ".ssa", ".vtt"):
                    old = base + ext
                    if old != sub.saved_path and os.path.exists(old):
                        os.remove(old)
                idx = skip_index + remaining.index(sub) + 1
                self._status(file_path, "alternative", sub.provider_name, idx, len(candidates))
                if self._on_complete:
                    self._on_complete(1, 0)
            else:
                self._status(file_path, "no_more")
                if self._on_complete:
                    self._on_complete(0, 1)
        except Exception as e:
            log.error(f"Alternative error: {os.path.basename(file_path)} — {e}")
            self._status(file_path, "error", self._friendly_error(e))
            if self._on_complete:
                self._on_complete(0, 1)
        finally:
            pool.terminate()

        if self._on_progress:
            self._on_progress(1.0)
