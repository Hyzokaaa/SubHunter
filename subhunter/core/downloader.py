import os
import threading
import subliminal
from babelfish import Language


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

    def _run(self, file_paths):
        total = len(file_paths)
        downloaded = 0
        failed = 0

        for i, path in enumerate(file_paths):
            if self._on_item_status:
                self._on_item_status(path, "searching")

            try:
                video = subliminal.scan_video(path)

                kwargs = {"providers": self.providers}
                if self.provider_configs:
                    kwargs["provider_configs"] = self.provider_configs

                subs = subliminal.download_best_subtitles(
                    {video}, self.languages, **kwargs
                )

                if subs.get(video):
                    if self.auto_rename:
                        for sub in subs[video]:
                            suffix = ""
                            # Add language suffix if multiple languages
                            if len(self.languages) > 1:
                                suffix = f".{sub.language.alpha3}"
                            out = os.path.splitext(path)[0] + suffix + ".srt"
                            with open(out, "wb") as f:
                                f.write(sub.content)
                    else:
                        subliminal.save_subtitles(video, subs[video])

                    downloaded += 1
                    if self._on_item_status:
                        self._on_item_status(path, "downloaded")
                else:
                    failed += 1
                    if self._on_item_status:
                        self._on_item_status(path, "not_found")

            except Exception:
                failed += 1
                if self._on_item_status:
                    self._on_item_status(path, "error")

            if self._on_progress:
                self._on_progress((i + 1) / total)

        if self._on_complete:
            self._on_complete(downloaded, failed)
