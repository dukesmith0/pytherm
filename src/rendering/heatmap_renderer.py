from __future__ import annotations

from PyQt6.QtGui import QColor

# Thermal gradient stops: (normalised_t, (R, G, B))
# Maps 0 → cold (blue) through to 1 → hot (red), matching the classic rainbow ramp.
_STOPS: list[tuple[float, tuple[int, int, int]]] = [
    (0.00, (0,   0,   255)),  # blue
    (0.25, (0,   255, 255)),  # cyan
    (0.50, (0,   255, 0)),    # green
    (0.75, (255, 255, 0)),    # yellow
    (1.00, (255, 0,   0)),    # red
]


def heatmap_color(temp_k: float, t_min_k: float, t_max_k: float) -> QColor:
    """Map a temperature to a color on the blue→cyan→green→yellow→red gradient.

    Temperatures outside [t_min_k, t_max_k] clamp to the endpoint colors.
    When t_min_k == t_max_k (uniform temperature field), returns the midpoint color.
    """
    if t_max_k <= t_min_k:
        t = 0.5
    else:
        t = (temp_k - t_min_k) / (t_max_k - t_min_k)
    t = max(0.0, min(1.0, t))

    for i in range(len(_STOPS) - 1):
        t0, c0 = _STOPS[i]
        t1, c1 = _STOPS[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return QColor(r, g, b)

    return QColor(255, 0, 0)  # should never reach here


def text_color_for_bg(bg: QColor) -> QColor:
    """Return black or white depending on which is more readable against bg."""
    lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
    return QColor(0, 0, 0) if lum > 128 else QColor(255, 255, 255)
