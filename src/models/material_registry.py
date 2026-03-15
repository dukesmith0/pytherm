from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from src.models.material import Material, load_materials


class MaterialRegistry:
    """Holds built-in and custom materials; persists custom ones to disk."""

    def __init__(self, builtin_path: Path, custom_path: Path) -> None:
        self._builtin_path = builtin_path
        self._custom_path = custom_path
        self._builtins: dict[str, Material] = load_materials(builtin_path, is_builtin=True)
        self._custom: dict[str, Material] = {}
        self._load_custom()

    # --- Read access ---

    @property
    def all_materials(self) -> dict[str, Material]:
        return {**self._builtins, **self._custom}

    @property
    def builtins(self) -> dict[str, Material]:
        return dict(self._builtins)

    @property
    def custom(self) -> dict[str, Material]:
        return dict(self._custom)

    def get(self, material_id: str) -> Material:
        return self.all_materials[material_id]

    # --- Write access (custom only) ---

    def add_or_update_custom(self, material: Material) -> None:
        self._custom[material.id] = material
        self.save_custom()

    def remove_custom(self, material_id: str) -> None:
        self._custom.pop(material_id, None)
        self.save_custom()

    def add_session_materials(self, materials: list[Material]) -> None:
        """Add materials for this session only -- does NOT write to disk."""
        for m in materials:
            self._custom[m.id] = m

    def generate_custom_id(self, name: str) -> str:
        """Derive a unique id from a display name."""
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "custom"
        candidate = base
        i = 1
        while candidate in self._builtins or candidate in self._custom:
            candidate = f"{base}_{i}"
            i += 1
        return candidate

    # --- Persistence ---

    def save_custom(self) -> None:
        self._custom_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "materials": [
                {
                    "id": m.id,
                    "name": m.name,
                    "color": m.color,
                    "k": m.k,
                    "rho": m.rho,
                    "cp": m.cp,
                    "note": m.note,
                    "abbr": m.abbr,
                    "category": m.category,
                }
                for m in self._custom.values()
            ]
        }
        tmp = self._custom_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self._custom_path)

    def _load_custom(self) -> None:
        if not self._custom_path.exists():
            return
        try:
            with open(self._custom_path) as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: could not load {self._custom_path}: {e}", file=sys.stderr)
            return  # corrupt file -- start with no custom materials
        for entry in data.get("materials", []):
            try:
                m = Material(**entry, is_builtin=False)
                self._custom[m.id] = m
            except Exception:
                pass  # skip malformed entries
