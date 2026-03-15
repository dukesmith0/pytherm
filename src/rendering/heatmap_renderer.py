from __future__ import annotations

from PyQt6.QtGui import QColor

_LUT_SIZE = 1024

# Named palette stop definitions: list of (position, (R, G, B))
_PALETTE_STOPS: dict[str, list[tuple[float, tuple[int, int, int]]]] = {
    "Classic": [
        (0.00, (0,   0,   255)),
        (0.25, (0,   255, 255)),
        (0.50, (0,   255, 0)),
        (0.75, (255, 255, 0)),
        (1.00, (255, 0,   0)),
    ],
    "Viridis": [
        (0.00, (68,  1,   84)),
        (0.25, (59,  82,  139)),
        (0.50, (33,  145, 140)),
        (0.75, (94,  201, 98)),
        (1.00, (253, 231, 37)),
    ],
    "Plasma": [
        (0.00, (13,  8,   135)),
        (0.25, (156, 23,  158)),
        (0.50, (237, 121, 83)),
        (0.75, (250, 200, 40)),
        (1.00, (240, 249, 33)),
    ],
    "Grayscale": [
        (0.00, (30,  30,  30)),
        (1.00, (240, 240, 240)),
    ],
}

PALETTE_NAMES: list[str] = list(_PALETTE_STOPS)


def _build_lut(stops: list[tuple[float, tuple[int, int, int]]]) -> list[QColor]:
    lut: list[QColor] = []
    for i in range(_LUT_SIZE):
        t = i / (_LUT_SIZE - 1)
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t <= t1:
                f = (t - t0) / (t1 - t0)
                lut.append(QColor(
                    int(c0[0] + f * (c1[0] - c0[0])),
                    int(c0[1] + f * (c1[1] - c0[1])),
                    int(c0[2] + f * (c1[2] - c0[2])),
                ))
                break
        else:
            lut.append(QColor(*stops[-1][1]))
    return lut


_LUTS: dict[str, list[QColor]] = {name: _build_lut(stops) for name, stops in _PALETTE_STOPS.items()}
_active_lut: list[QColor] = _LUTS["Classic"]
_active_palette_name: str = "Classic"
_reversed: bool = False


def set_palette(name: str) -> None:
    """Switch the active heatmap color palette. Name must be one of PALETTE_NAMES."""
    global _active_lut, _active_palette_name
    _active_palette_name = name if name in _LUTS else "Classic"
    _active_lut = _LUTS[_active_palette_name]


def set_reversed(rev: bool) -> None:
    """Flip the palette so hot=blue and cold=red."""
    global _reversed
    _reversed = rev


def is_reversed() -> bool:
    return _reversed


def active_palette_name() -> str:
    return _active_palette_name


def heatmap_color(temp_k: float, t_min_k: float, t_max_k: float) -> QColor:
    """Map a temperature to a color using the active palette.

    Temperatures outside [t_min_k, t_max_k] clamp to the endpoint colors.
    When t_min_k == t_max_k (uniform temperature field), returns the midpoint color.
    """
    if t_max_k <= t_min_k:
        return _active_lut[_LUT_SIZE // 2]
    t = (temp_k - t_min_k) / (t_max_k - t_min_k)
    t = max(0.0, min(1.0, t))
    if _reversed:
        t = 1.0 - t
    idx = int(t * (_LUT_SIZE - 1))
    return _active_lut[idx]


def text_color_for_bg(bg: QColor) -> QColor:
    """Return black or white depending on which is more readable against bg."""
    lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
    return QColor(0, 0, 0) if lum > 128 else QColor(255, 255, 255)
