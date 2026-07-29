import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".subhunter")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "theme": "dark",
    "default_language": "Espanol",
    "auto_rename": True,
    "languages": ["Espanol"],
    "providers": {
        "opensubtitlescom": True,
        "opensubtitles": True,
        "subtitulamos": True,
        "addic7ed": True,
        "gestdown": True,
        "bsplayer": True,
        "subtis": True,
        "podnapisi": False,
        "tvsubtitles": False,
    },
    "opensubtitlescom_username": "",
    "opensubtitlescom_password": "",
}

PROVIDER_LABELS = {
    "opensubtitlescom": "OpenSubtitles.com (nuevo)",
    "opensubtitles": "OpenSubtitles.org (clasico)",
    "subtitulamos": "Subtitulamos.tv",
    "addic7ed": "Addic7ed",
    "gestdown": "Gestdown",
    "podnapisi": "Podnapisi",
    "tvsubtitles": "TVSubtitles",
    "bsplayer": "BSPlayer",
    "subtis": "Subtis",
}


class Config:
    """Persistent JSON config with defaults."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge saved over defaults (keeps new keys from DEFAULTS)
                for k, v in saved.items():
                    if k == "providers" and isinstance(v, dict):
                        self._data["providers"].update(v)
                    else:
                        self._data[k] = v
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def get_active_providers(self) -> list[str]:
        return [p for p, on in self._data["providers"].items() if on]

    def get_provider_config(self) -> dict:
        """Build subliminal provider_configs dict from credentials."""
        cfg = {}
        user = self._data.get("opensubtitlescom_username", "").strip()
        pwd = self._data.get("opensubtitlescom_password", "").strip()
        if user and pwd:
            cfg["opensubtitlescom"] = {"username": user, "password": pwd}
        return cfg

    @property
    def data(self):
        return self._data
