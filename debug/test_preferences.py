"""Tests for src.models.preferences.Preferences."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.models.preferences import Preferences


def test_smooth_step_default():
    assert Preferences().smooth_step is False


def test_step_history_size_default():
    assert Preferences().step_history_size == 20


def test_save_load_round_trip():
    p = Preferences(smooth_step=True, step_history_size=50)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        p.save(path)
        loaded = Preferences.load(path)
        assert loaded.smooth_step is True
        assert loaded.step_history_size == 50


def test_load_ignores_unknown_fields():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        path.write_text(json.dumps({"unit": "K", "future_field": 42}), encoding="utf-8")
        loaded = Preferences.load(path)
        assert loaded.unit == "K"


def test_theme_default():
    assert Preferences().theme == "dark"


def test_save_load_theme():
    p = Preferences(theme="light")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        p.save(path)
        loaded = Preferences.load(path)
        assert loaded.theme == "light"


def test_save_load_v100_fields():
    p = Preferences(
        reverse_palette=True,
        isotherm_line_width=4,
        heatmap_auto_init=False,
        heatmap_scale_mode="live",
    )
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        p.save(path)
        loaded = Preferences.load(path)
        assert loaded.reverse_palette is True
        assert loaded.isotherm_line_width == 4
        assert loaded.heatmap_auto_init is False
        assert loaded.heatmap_scale_mode == "live"


# ── _clamp() validation (v1.1.0 security hardening) ─────────────────────────

def test_clamp_sim_speed_range():
    p = Preferences(sim_speed=0.01)
    p._clamp()
    assert p.sim_speed >= 0.1
    p2 = Preferences(sim_speed=5000.0)
    p2._clamp()
    assert p2.sim_speed <= 1000.0


def test_clamp_default_rows_range():
    p = Preferences(default_rows=0)
    p._clamp()
    assert p.default_rows >= 1
    p2 = Preferences(default_rows=999)
    p2._clamp()
    assert p2.default_rows <= 200


def test_clamp_step_history_size_range():
    p = Preferences(step_history_size=1)
    p._clamp()
    assert p.step_history_size >= 5
    p2 = Preferences(step_history_size=999)
    p2._clamp()
    assert p2.step_history_size <= 200


def test_load_applies_clamping():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        path.write_text(json.dumps({
            "ambient_temp_k": -50.0,
            "default_rows": 500,
        }), encoding="utf-8")
        loaded = Preferences.load(path)
        assert loaded.ambient_temp_k >= 0.0
        assert loaded.default_rows <= 200
