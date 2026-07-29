import os
import threading
import traceback
import subliminal
from babelfish import Language
from .logger import log

# Configure subliminal cache (required for providers like subtitulamos)
try:
    subliminal.region.configure('dogpile.cache.memory')
except Exception:
    pass  # Already configured

# Reduce default timeout from 10s to 5s for faster failures
import socket
socket.setdefaulttimeout(5)


class SubtitleDownloader:
    """Handles subtitle search and download in a background thread."""

    def __init__(self, lang_codes=None, auto_rename=True,
                 providers=None, provider_configs=None):
        if lang_codes is None:
            lang_codes = ["spa"]
        self.languages = {Language(code) for code in lang_codes}
        self.auto_rename = auto_rename
        self.providers = providers
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
        thread = threading.Thread(
            target=self._run, args=(file_paths,), daemon=True
        )
        thread.start()

    def search(self, file_paths, on_results=None):
        """Search all providers and return results without downloading."""
        thread = threading.Thread(
            target=self._run_search, args=(file_paths, on_results), daemon=True
        )
        thread.start()

    def download_selection(self, selections, fallbacks=None):
        """Download specific subtitle objects with fallback alternatives.
        selections: dict filepath -> subtitle_obj
        fallbacks: dict filepath -> list of (sub, score, provider) tuples
        """
        thread = threading.Thread(
            target=self._run_selection, args=(selections, fallbacks), daemon=True
        )
        thread.start()

    def download_alternative(self, file_path, skip_index=0):
        """Download an alternative subtitle, skipping the first N results."""
        thread = threading.Thread(
            target=self._run_alternative, args=(file_path, skip_index), daemon=True
        )
        thread.start()

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

    def _build_kwargs(self):
        kwargs = {"providers": self.providers}
        if self.provider_configs:
            kwargs["provider_configs"] = self.provider_configs
        return kwargs

    def _save_subtitle(self, path, sub):
        if self.auto_rename:
            suffix = ""
            if len(self.languages) > 1:
                suffix = f".{sub.language.alpha3}"
            out = os.path.splitext(path)[0] + suffix + ".srt"
            with open(out, "wb") as f:
                f.write(sub.content)
        else:
            video = subliminal.scan_video(path)
            subliminal.save_subtitles(video, [sub])

    def _run(self, file_paths):
        total = len(file_paths)
        downloaded = 0
        failed = 0
        log.info(f"Download batch started: {total} files")

        for i, path in enumerate(file_paths):
            fname = os.path.basename(path)
            log.debug(f"Processing: {fname}")
            if self._on_item_status:
                self._on_item_status(path, "searching")

            try:
                video = subliminal.scan_video(path)
                subs = subliminal.download_best_subtitles(
                    {video}, self.languages, **self._build_kwargs()
                )

                if subs.get(video):
                    for sub in subs[video]:
                        self._save_subtitle(path, sub)

                    provider = subs[video][0].provider_name
                    downloaded += 1
                    log.info(f"OK: {fname} from {provider}")
                    if self._on_item_status:
                        self._on_item_status(path, "downloaded", provider)
                else:
                    failed += 1
                    log.warning(f"Not found: {fname}")
                    if self._on_item_status:
                        self._on_item_status(path, "not_found")

            except Exception as e:
                failed += 1
                log.error(f"Error: {fname} — {e}\n{traceback.format_exc()}")
                if self._on_item_status:
                    self._on_item_status(path, "error", self._friendly_error(e))

            if self._on_progress:
                self._on_progress((i + 1) / total)

        if self._on_complete:
            self._on_complete(downloaded, failed)

    def _run_search(self, file_paths, on_results):
        """Search all providers using a shared pool with reduced timeout."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time

        results = {}
        total = len(file_paths)
        log.info(f"Search started: {total} files")

        # Scan all videos first (fast, local)
        videos = {}
        for path in file_paths:
            fname = os.path.basename(path)
            try:
                videos[path] = subliminal.scan_video(path)
            except Exception as e:
                results[path] = []
                log.error(f"Scan error: {fname} — {e}")
                if self._on_item_status:
                    self._on_item_status(path, "error", self._friendly_error(e))

        # Search with a single shared pool (reuses connections)
        pool = subliminal.core.ProviderPool(
            providers=self.providers,
            provider_configs=self.provider_configs,
        )

        completed = 0
        try:
            for path, video in videos.items():
                fname = os.path.basename(path)
                log.debug(f"Searching: {fname}")
                if self._on_item_status:
                    self._on_item_status(path, "searching")

                try:
                    candidates = pool.list_subtitles(video, self.languages)
                    scored = []
                    for sub in candidates:
                        score = subliminal.compute_score(sub, video)
                        scored.append((sub, score, sub.provider_name))

                    scored.sort(key=lambda x: x[1], reverse=True)
                    results[path] = scored

                    if scored:
                        providers = ", ".join(set(s[2] for s in scored))
                        log.info(f"Found {len(scored)} subs for {fname}: [{providers}]")
                        if self._on_item_status:
                            self._on_item_status(path, "found", len(scored))
                    else:
                        log.warning(f"No subs found for {fname}")
                        if self._on_item_status:
                            self._on_item_status(path, "not_found")

                except Exception as e:
                    results[path] = []
                    log.error(f"Search error: {fname} — {e}")
                    if self._on_item_status:
                        self._on_item_status(path, "error", self._friendly_error(e))

                completed += 1
                if self._on_progress:
                    self._on_progress(completed / total)
        finally:
            pool.terminate()

        if on_results:
            on_results(results)

    def _run_selection(self, selections, fallbacks=None):
        """Download specific subtitle objects chosen by user, with auto-fallback."""
        import time
        total = len(selections)
        downloaded = 0
        failed = 0
        failed_items = []
        fallbacks = fallbacks or {}

        log.info(f"Download selection started: {total} files")

        provider_pool = subliminal.core.ProviderPool(
            providers=self.providers,
            provider_configs=self.provider_configs,
        )

        try:
            for i, (path, chosen_sub) in enumerate(selections.items()):
                if self._on_item_status:
                    self._on_item_status(path, "searching")

                attempts = [chosen_sub]
                for sub, _score, _prov in fallbacks.get(path, []):
                    if sub is not chosen_sub:
                        attempts.append(sub)

                success = False
                fname = os.path.basename(path)
                for attempt in attempts:
                    try:
                        provider_pool.download_subtitle(attempt)
                        if attempt.content:
                            self._save_subtitle(path, attempt)
                            downloaded += 1
                            provider = attempt.provider_name
                            if attempt is not chosen_sub:
                                log.info(f"OK (fallback): {fname} from {provider}")
                                if self._on_item_status:
                                    self._on_item_status(
                                        path, "downloaded",
                                        f"{provider} (fallback)"
                                    )
                            else:
                                log.info(f"OK: {fname} from {provider}")
                                if self._on_item_status:
                                    self._on_item_status(path, "downloaded", provider)
                            success = True
                            break
                    except Exception as e:
                        log.debug(f"Provider {attempt.provider_name} failed for {fname}: {e}")
                        continue

                if not success:
                    failed_items.append((path, chosen_sub))
                    log.warning(f"First pass failed for {fname}, will retry")

                if self._on_progress:
                    self._on_progress((i + 1) / total)

                # Small delay between downloads to avoid rate limiting
                time.sleep(0.5)

        finally:
            provider_pool.terminate()

        # Retry failed items with a fresh provider pool
        if failed_items:
            log.info(f"Retrying {len(failed_items)} failed downloads with fresh pool")
            time.sleep(2)

            retry_pool = subliminal.core.ProviderPool(
                providers=self.providers,
                provider_configs=self.provider_configs,
            )
            try:
                for path, chosen_sub in failed_items:
                    fname = os.path.basename(path)
                    if self._on_item_status:
                        self._on_item_status(path, "searching")

                    attempts = [chosen_sub]
                    for sub, _score, _prov in fallbacks.get(path, []):
                        if sub is not chosen_sub:
                            attempts.append(sub)

                    success = False
                    for attempt in attempts:
                        try:
                            retry_pool.download_subtitle(attempt)
                            if attempt.content:
                                self._save_subtitle(path, attempt)
                                downloaded += 1
                                provider = attempt.provider_name
                                log.info(f"OK (retry): {fname} from {provider}")
                                if self._on_item_status:
                                    self._on_item_status(
                                        path, "downloaded",
                                        f"{provider} (retry)"
                                    )
                                success = True
                                break
                        except Exception as e:
                            log.debug(f"Retry: {attempt.provider_name} failed for {fname}: {e}")
                            continue

                    if not success:
                        failed += 1
                        log.error(f"All providers failed for {fname} (after retry)")
                        if self._on_item_status:
                            self._on_item_status(path, "error", "Todos los proveedores fallaron")

                    time.sleep(0.5)
            finally:
                retry_pool.terminate()

        if self._on_complete:
            self._on_complete(downloaded, failed)

    def _run_alternative(self, file_path, skip_index):
        if self._on_item_status:
            self._on_item_status(file_path, "searching")

        try:
            video = subliminal.scan_video(file_path)

            # List ALL available subtitles instead of just the best
            kwargs = self._build_kwargs()
            all_subs = subliminal.list_subtitles(
                {video}, self.languages, **kwargs
            )

            candidates = all_subs.get(video, [])

            # Sort by score (subliminal's default scoring)
            candidates.sort(
                key=lambda s: subliminal.compute_score(s, video),
                reverse=True
            )

            if skip_index >= len(candidates):
                if self._on_item_status:
                    self._on_item_status(file_path, "no_more")
                if self._on_complete:
                    self._on_complete(0, 1)
                return

            # Skip the first N and pick the next one
            target = candidates[skip_index]

            # Download the subtitle content
            provider_name = target.provider_name
            provider_pool = subliminal.core.ProviderPool(
                providers=self.providers,
                provider_configs=self.provider_configs,
            )
            try:
                provider_pool.download_subtitle(target)
            finally:
                provider_pool.terminate()

            if target.content:
                # Delete existing .srt before saving new one
                srt_path = os.path.splitext(file_path)[0] + ".srt"
                if os.path.exists(srt_path):
                    os.remove(srt_path)

                self._save_subtitle(file_path, target)

                remaining = len(candidates) - skip_index - 1
                if self._on_item_status:
                    self._on_item_status(
                        file_path, "alternative",
                        provider_name, skip_index + 1, len(candidates)
                    )
                if self._on_complete:
                    self._on_complete(1, 0)
            else:
                # Content failed to download, try next
                self._run_alternative(file_path, skip_index + 1)

        except Exception as e:
            if self._on_item_status:
                self._on_item_status(file_path, "error", self._friendly_error(e))
            if self._on_complete:
                self._on_complete(0, 1)

        if self._on_progress:
            self._on_progress(1.0)
