from __future__ import annotations

import sys
from pathlib import Path


def _root() -> Path:
    """Project root in dev mode; PyInstaller extraction dir in a frozen exe."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # src/utils/paths.py -> src/utils -> src -> project root
    return Path(__file__).parent.parent.parent


def get_bundle_data_dir() -> Path:
    """Read-only bundled data directory (materials.json, etc.)."""
    return _root() / "data"


def get_user_data_dir() -> Path:
    """Writable user data directory (preferences, user materials, recent files).

    In a frozen exe this is a 'data' folder next to the executable so the user
    can edit preferences without needing write access to the bundle itself.
    """
    if hasattr(sys, "_MEIPASS"):
        d = Path(sys.executable).parent / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return _root() / "data"


def get_templates_dir() -> Path:
    """Read-only bundled templates directory."""
    return _root() / "templates"
