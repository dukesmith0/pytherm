from __future__ import annotations

import json
import os
from pathlib import Path

_RECENT_PATH = Path(__file__).parent.parent.parent / "data" / "recent_files.json"
_MAX_RECENT = 10


def load_recent() -> list[str]:
    if not _RECENT_PATH.exists():
        return []
    try:
        data = json.loads(_RECENT_PATH.read_text(encoding="utf-8"))
        return [p for p in data if isinstance(p, str) and Path(p).exists()][:_MAX_RECENT]
    except Exception:
        return []


def _write_recent(files: list[str]) -> None:
    _RECENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _RECENT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(files, indent=2), encoding="utf-8")
    os.replace(tmp, _RECENT_PATH)


def add_recent(path: str) -> list[str]:
    norm = str(Path(path).resolve())
    files = load_recent()
    files = [f for f in files if str(Path(f).resolve()) != norm]
    files.insert(0, path)
    files = files[:_MAX_RECENT]
    _write_recent(files)
    return files


def remove_recent(path: str) -> list[str]:
    files = load_recent()
    if path in files:
        files.remove(path)
        _write_recent(files)
    return files
