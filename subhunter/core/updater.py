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
        new_exe = None
        try:
            # Determine current exe path
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                import webbrowser
                webbrowser.open(download_url)
                if self._on_download_done:
                    self._on_download_done()
                return

            exe_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            new_exe = os.path.join(exe_dir, f"{exe_name}.update")

            # Download with progress — no timeout on read, only on connect
            req = urllib.request.Request(download_url, headers={"User-Agent": "SubHunter"})
            resp = urllib.request.urlopen(req, timeout=15)

            # Follow redirect to actual file URL
            actual_url = resp.geturl()
            resp.close()
            req2 = urllib.request.Request(actual_url, headers={"User-Agent": "SubHunter"})
            resp = urllib.request.urlopen(req2, timeout=15)

            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0

            with open(new_exe, 'wb') as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and self._on_download_progress:
                        self._on_download_progress(int(downloaded * 100 / total))

            resp.close()

            # Verify download is complete
            actual_size = os.path.getsize(new_exe)
            if total > 0 and actual_size != total:
                raise RuntimeError(f"Download incompleto: {actual_size}/{total} bytes")

            # Minimum size check (should be at least 10MB for a PyInstaller exe)
            if actual_size < 10_000_000:
                raise RuntimeError(f"Archivo muy pequeno: {actual_size} bytes")

            if self._on_download_done:
                self._on_download_done()

            # Get the PID of the current process so the updater script
            # can wait for BOTH the child (this process) and the parent
            # bootloader process to fully exit before replacing the exe.
            # In PyInstaller onefile mode, the parent bootloader cleans up
            # the _MEI temp folder after the child exits. If we launch the
            # new exe before the parent finishes, extraction can fail.
            current_pid = os.getpid()
            exe_name_only = os.path.splitext(exe_name)[0]

            # Create PowerShell updater script
            ps_path = os.path.join(tempfile.gettempdir(), "subhunter_update.ps1")
            # Escape backslashes for PowerShell
            cur = current_exe.replace("'", "''")
            new = new_exe.replace("'", "''")
            ps_content = f"""
# Wait for the current application process (and its parent bootloader)
# to fully exit. The PyInstaller onefile bootloader is a parent process
# that cleans up _MEI temp files after the child exits.
$exeName = '{exe_name_only}'
for ($i = 0; $i -lt 30; $i++) {{
    $procs = Get-Process -Name $exeName -ErrorAction SilentlyContinue
    if (-not $procs) {{ break }}
    Start-Sleep -Seconds 1
}}

# Extra safety pause for file handle release
Start-Sleep -Seconds 2

# Delete old exe with retry
for ($i = 0; $i -lt 20; $i++) {{
    try {{
        if (Test-Path '{cur}') {{
            Remove-Item '{cur}' -Force -ErrorAction Stop
        }}
        break
    }} catch {{
        Start-Sleep -Seconds 1
    }}
}}

# Move new exe into place
Move-Item -Path '{new}' -Destination '{cur}' -Force

# Wait for filesystem to settle
Start-Sleep -Seconds 1

# Launch the new exe with PYINSTALLER_RESET_ENVIRONMENT so the
# bootloader unpacks to a fresh _MEI folder and resets all internal
# environment variables (avoids reusing stale _MEI paths).
$env:PYINSTALLER_RESET_ENVIRONMENT = '1'
Start-Process '{cur}'

# Clean up this script
Remove-Item $MyInvocation.MyCommand.Path -Force
"""
            with open(ps_path, 'w', encoding='utf-8') as f:
                f.write(ps_content)

            # Launch PowerShell updater and exit
            subprocess.Popen(
                ['powershell', '-ExecutionPolicy', 'Bypass',
                 '-WindowStyle', 'Hidden', '-File', ps_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            os._exit(0)

        except Exception as e:
            try:
                if new_exe and os.path.exists(new_exe):
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
