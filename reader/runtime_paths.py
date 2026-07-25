"""
Path resolution that works the same from a source checkout and from a PyInstaller build.

Two roots exist and must not be confused:

- ``resource_root()`` is read-only. In a frozen build it is the temporary extraction
  directory (``sys._MEIPASS``), which is wiped on exit and may sit under Program Files.
- ``user_data_root()`` is writable and survives restarts. Config and any future local
  exports go here.

Writing an export into ``resource_root()`` would either fail on a locked-down install or
silently vanish when the process exits, so the two are kept apart deliberately.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "ZairyuReader"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Read-only root holding static/, tools/ and resources/."""
    bundle_dir = getattr(sys, "_MEIPASS", "")
    if is_frozen() and bundle_dir:
        return Path(bundle_dir)
    return Path(__file__).resolve().parents[1]


def user_data_root() -> Path:
    """Writable per-user root for the standalone local reader."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


def static_dir() -> Path:
    return resource_root() / "static"


def trust_anchor_manifest() -> Path:
    return resource_root() / "resources" / "moj" / "trust-anchors" / "manifest.json"


def ocr_resources_dir() -> Path:
    """Read-only packaged OCR assets; these are never downloaded at runtime."""
    return resource_root() / "resources" / "ocr"


def ocr_model_dir() -> Path:
    """The sole bundled PaddleOCR recognizer asset directory."""
    return ocr_resources_dir() / "ppocrv6"


def countries_ja_path() -> Path:
    return resource_root() / "resources" / "moj" / "trust-anchors" / "countries" / "countries_ja.json"


def env_path() -> Path:
    """
    Local ``.env`` overrides.

    A frozen build has no repo-root ``.env``, so administrators drop one next to the
    executable or into the per-user data directory.
    """
    if is_frozen():
        candidate = Path(sys.executable).resolve().parent / ".env"
        if candidate.exists():
            return candidate
        return user_data_root() / ".env"
    return resource_root() / ".env"
