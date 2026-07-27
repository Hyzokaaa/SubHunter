import threading
import urllib.request
import json
import webbrowser

VERSION = "1.0.0"
REPO = "Hyzokaaa/SubHunter"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"


class Updater:
    """Checks GitHub releases for a newer version."""

    def __init__(self):
        self._on_update_available = None

    def on_update_available(self, callback):
        """callback(latest_version, download_url)"""
        self._on_update_available = callback

    def check(self):
        thread = threading.Thread(target=self._check, daemon=True)
        thread.start()

    def _check(self):
        try:
            req = urllib.request.Request(API_URL, headers={"User-Agent": "SubHunter"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            tag = data.get("tag_name", "").lstrip("v")
            if not tag:
                return

            if self._is_newer(tag, VERSION):
                # Find .exe asset URL
                download_url = RELEASES_URL
                for asset in data.get("assets", []):
                    if asset["name"].endswith(".exe"):
                        download_url = asset["browser_download_url"]
                        break

                if self._on_update_available:
                    self._on_update_available(tag, download_url)

        except Exception:
            pass  # Silent fail — no internet, API down, etc.

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        try:
            lat = tuple(int(x) for x in latest.split("."))
            cur = tuple(int(x) for x in current.split("."))
            return lat > cur
        except ValueError:
            return False

    @staticmethod
    def open_download(url: str):
        webbrowser.open(url)
