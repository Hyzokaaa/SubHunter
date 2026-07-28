import os
import sys
import threading
import tempfile
import subprocess
import urllib.request
import json

VERSION = "1.1.0"
REPO = "Hyzokaaa/SubHunter"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"


class Updater:
    """Checks GitHub releases for a newer version and handles self-update."""

    def __init__(self):
        self._on_update_available = None
        self._on_download_progress = None
        self._on_download_done = None
        self._on_download_error = None
        self._download_url = None

    def on_update_available(self, callback):
        """callback(latest_version, download_url)"""
        self._on_update_available = callback

    def on_download_progress(self, callback):
        """callback(percent: int)"""
        self._on_download_progress = callback

    def on_download_done(self, callback):
        """callback()"""
        self._on_download_done = callback

    def on_download_error(self, callback):
        """callback(error_msg: str)"""
        self._on_download_error = callback

    def check(self):
        thread = threading.Thread(target=self._check, daemon=True)
        thread.start()

    def download_and_replace(self, download_url):
        thread = threading.Thread(
            target=self._download_and_replace, args=(download_url,), daemon=True
        )
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
                download_url = RELEASES_URL
                for asset in data.get("assets", []):
                    if asset["name"].endswith(".exe"):
                        download_url = asset["browser_download_url"]
                        break

                if self._on_update_available:
                    self._on_update_available(tag, download_url)

        except Exception:
            pass

    def _download_and_replace(self, download_url):
        try:
            # Determine current exe path
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                # Running from source — can't self-update, open browser instead
                import webbrowser
                webbrowser.open(download_url)
                if self._on_download_done:
                    self._on_download_done()
                return

            exe_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            new_exe = os.path.join(exe_dir, f"{exe_name}.new")

            # Download with progress
            req = urllib.request.Request(download_url, headers={"User-Agent": "SubHunter"})
            resp = urllib.request.urlopen(req, timeout=30)
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 65536

            with open(new_exe, 'wb') as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and self._on_download_progress:
                        self._on_download_progress(int(downloaded * 100 / total))

            resp.close()

            # Create updater .bat script
            bat_path = os.path.join(tempfile.gettempdir(), "subhunter_update.bat")
            bat_content = f'''@echo off
echo Actualizando SubHunter...
:wait
ping 127.0.0.1 -n 2 > nul
del "{current_exe}" 2>nul
if exist "{current_exe}" goto wait
move "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
'''
            with open(bat_path, 'w') as f:
                f.write(bat_content)

            if self._on_download_done:
                self._on_download_done()

            # Launch the bat and exit
            subprocess.Popen(
                ['cmd', '/c', bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            os._exit(0)

        except Exception as e:
            # Clean up failed download
            try:
                if os.path.exists(new_exe):
                    os.remove(new_exe)
            except Exception:
                pass

            if self._on_download_error:
                self._on_download_error(str(e))

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        try:
            lat = tuple(int(x) for x in latest.split("."))
            cur = tuple(int(x) for x in current.split("."))
            return lat > cur
        except ValueError:
            return False
