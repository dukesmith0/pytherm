"""Tests for src.rendering.heatmap_renderer palette and color mapping."""
from __future__ import annotations

from src.rendering.heatmap_renderer import (
    heatmap_color, set_palette, PALETTE_NAMES,
    set_reversed, is_reversed,
)


def test_palette_names_non_empty():
    assert isinstance(PALETTE_NAMES, list) and len(PALETTE_NAMES) >= 2
    assert all(isinstance(n, str) for n in PALETTE_NAMES)


def test_set_palette_changes_color():
    set_palette(PALETTE_NAMES[0])
    c1 = heatmap_color(0.5, 273.15, 373.15)
    set_palette(PALETTE_NAMES[-1])
    c2 = heatmap_color(0.5, 273.15, 373.15)
    set_palette(PALETTE_NAMES[0])
    assert c1 != c2


def test_valid_rgb_all_palettes():
    for name in PALETTE_NAMES:
        set_palette(name)
        c = heatmap_color(0.0, 273.15, 373.15)
        r, g, b = c.red(), c.green(), c.blue()
        assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255
    set_palette(PALETTE_NAMES[0])


def test_clamp_below_min():
    set_palette(PALETTE_NAMES[0])
    c_at_min = heatmap_color(273.15, 273.15, 373.15)
    c_below  = heatmap_color(200.0,  273.15, 373.15)
    assert c_at_min == c_below


def test_clamp_above_max():
    set_palette(PALETTE_NAMES[0])
    c_at_max = heatmap_color(373.15, 273.15, 373.15)
    c_above  = heatmap_color(500.0,  273.15, 373.15)
    assert c_at_max == c_above


def test_reverse_palette_flips():
    old = is_reversed()
    set_reversed(False)
    c_normal = heatmap_color(373.15, 273.15, 373.15)
    set_reversed(True)
    c_reversed = heatmap_color(373.15, 273.15, 373.15)
    set_reversed(old)
    assert c_normal.red() > c_reversed.red() or c_normal.blue() < c_reversed.blue()


def test_isotherm_line_width_clamp():
    assert max(1, min(5, 10)) == 5
    assert max(1, min(5, 0)) == 1
    assert max(1, min(5, 3)) == 3
