import copy
import json
import os

from .constants import DEFAULT_PROVIDERS

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".subhunter")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

CONFIG_VERSION = 2

DEFAULTS = {
    "config_version": CONFIG_VERSION,
    "theme": "dark",
    "default_language": "Espanol",
    "auto_rename": True,
    "auto_sync": True,
    "languages": ["Espanol"],
    # name -> enabled; providers missing here use DEFAULT_PROVIDERS
    "providers": {},
    # name -> {field: value} (usernames, passwords, API keys...)
    "provider_settings": {},
}


class Config:
    """Persistent JSON config with defaults."""

    def __init__(self):
        self._data = copy.deepcopy(DEFAULTS)
        self._load()

    def _load(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        if saved.get("config_version", 1) < 2:
            saved = self._migrate_v1(saved)
        # Merge saved over defaults (keeps new keys from DEFAULTS)
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(self._data.get(k), dict):
                self._data[k].update(v)
            else:
                self._data[k] = v

    @staticmethod
    def _migrate_v1(saved):
        """v1 (<= 1.4) had a fixed provider list and OpenSubtitles.com credentials only."""
        saved = dict(saved)
        # The provider set changed completely: start from the new defaults
        saved["providers"] = {}
        user = saved.pop("opensubtitlescom_username", "").strip()
        pwd = saved.pop("opensubtitlescom_password", "").strip()
        if user and pwd:
            saved["provider_settings"] = {
                "opensubtitlescom": {"username": user, "password": pwd},
            }
        saved["config_version"] = CONFIG_VERSION
        return saved

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def is_provider_enabled(self, name) -> bool:
        return self._data["providers"].get(name, name in DEFAULT_PROVIDERS)

    def get_provider_settings(self, name) -> dict:
        return {k: v for k, v in self._data["provider_settings"].get(name, {}).items() if v}

    def get_active_providers(self) -> list[str]:
        """Enabled providers that have the configuration they need."""
        from .providers import provider_catalog
        active = []
        for p in provider_catalog():
            if not self.is_provider_enabled(p["name"]):
                continue
            if p["needs_config"] and not self.get_provider_settings(p["name"]):
                continue
            active.append(p["name"])
        return active

    def get_provider_config(self) -> dict:
        """Build subliminal provider_configs dict from saved settings."""
        from .providers import DEFAULT_OPTIONS
        cfg = {name: dict(opts) for name, opts in DEFAULT_OPTIONS.items()}
        for name in self._data["provider_settings"]:
            settings = self.get_provider_settings(name)
            if settings:
                cfg.setdefault(name, {}).update(settings)
        return cfg

    @property
    def data(self):
        return self._data
