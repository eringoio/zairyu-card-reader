"""Local-only reader configuration with safe migration of the former agent config."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_APP_VERSION = "0.2.1"


@dataclass
class LocalConfig:
    reader_id: int = 0
    app_version: str = DEFAULT_APP_VERSION

    def safe_dict(self) -> dict[str, int | str]:
        return {"reader_id": self.reader_id, "app_version": self.app_version}


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    return base / "ZairyuReader" / "config.json"


class LocalConfigStore:
    """JSON configuration that deliberately retains no remote-integration state."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_config_path()

    def load(self) -> LocalConfig:
        if not self.path.exists():
            return LocalConfig()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("config is not an object")
            config = LocalConfig(reader_id=max(0, int(data.get("reader_id", 0) or 0)), app_version=DEFAULT_APP_VERSION)
            # Saving replaces legacy remote settings without reading or logging them.
            if set(data) - {"reader_id", "app_version", "config_version"}:
                self.save(config)
            return config
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # A malformed legacy file is safely replaced with defaults where possible.
            config = LocalConfig()
            try:
                self.save(config)
            except OSError:
                pass
            return config

    def save(self, config: LocalConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"config_version": 2, **asdict(config)}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
