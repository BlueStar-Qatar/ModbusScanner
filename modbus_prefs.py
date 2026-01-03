from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def preferences_path() -> Path:
    return Path.home() / ".modbus_scanner" / "preferences.json"


class PreferencesStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or preferences_path()
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        try:
            raw = self.path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                self.data = parsed
            else:
                self.data = {}
        except FileNotFoundError:
            self.data = {}
        except Exception:
            self.data = {}
        return self.data

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, indent=2, ensure_ascii=False)
        self.path.write_text(payload, encoding="utf-8")
        return self.path

    def get_theme(self, default: str = "light") -> str:
        ui = self.data.get("ui")
        if isinstance(ui, dict):
            value = ui.get("theme")
            if value in {"light", "dark"}:
                return str(value)
        return default

    def set_theme(self, mode: str) -> None:
        mode = "dark" if mode == "dark" else "light"
        ui = self.data.get("ui")
        if not isinstance(ui, dict):
            ui = {}
            self.data["ui"] = ui
        ui["theme"] = mode

    def get_profiles(self) -> Dict[str, Any]:
        profiles = self.data.get("profiles")
        return profiles if isinstance(profiles, dict) else {}

    def set_profiles(self, profiles: Dict[str, Any]) -> None:
        self.data["profiles"] = profiles

    def get_last_profile(self, default: str = "Default") -> str:
        value = self.data.get("last_profile")
        return str(value) if value else default

    def set_last_profile(self, name: str) -> None:
        self.data["last_profile"] = str(name)

    def get_last_used_scan(self) -> Optional[Dict[str, Any]]:
        value = self.data.get("last_used_scan")
        return value if isinstance(value, dict) else None

    def set_last_used_scan(self, config: Dict[str, Any]) -> None:
        self.data["last_used_scan"] = dict(config)

    def get_last_used_read(self) -> Optional[Dict[str, Any]]:
        value = self.data.get("last_used_read")
        return value if isinstance(value, dict) else None

    def set_last_used_read(self, config: Dict[str, Any]) -> None:
        self.data["last_used_read"] = dict(config)
