from __future__ import annotations

from enum import Enum

from PyQt6.QtGui import QValidator
from PyQt6.QtWidgets import QDoubleSpinBox


class Unit(str, Enum):
    CELSIUS    = "°C"
    KELVIN     = "K"
    FAHRENHEIT = "°F"
    RANKINE    = "R"


_active: Unit = Unit.CELSIUS


def set_unit(u: Unit) -> None:
    global _active
    _active = u


def active() -> Unit:
    return _active


def to_display(k: float) -> float:
    """Convert Kelvin to the current display unit."""
    if _active == Unit.CELSIUS:
        return k - 273.15
    if _active == Unit.KELVIN:
        return k
    if _active == Unit.FAHRENHEIT:
        return (k - 273.15) * 9.0 / 5.0 + 32.0
    return k * 9.0 / 5.0  # Rankine


def from_display(v: float) -> float:
    """Convert a displayed value back to Kelvin."""
    if _active == Unit.CELSIUS:
        return v + 273.15
    if _active == Unit.KELVIN:
        return v
    if _active == Unit.FAHRENHEIT:
        return (v - 32.0) * 5.0 / 9.0 + 273.15
    return v * 5.0 / 9.0  # Rankine


def suffix() -> str:
    return _active.value


def spinbox_range() -> tuple[float, float]:
    """(min, max) in the current display unit."""
    if _active == Unit.CELSIUS:
        return -273.15, 10000.0
    if _active == Unit.KELVIN:
        return 0.0, 10273.15
    if _active == Unit.FAHRENHEIT:
        return -459.67, 18032.0
    return 0.0, 18491.67  # Rankine


def fmt_energy(j: float) -> str:
    """Format energy in Joules with auto-scaled SI prefix (J, kJ, MJ, GJ)."""
    abs_j = abs(j)
    if abs_j >= 1e9:
        return f"{j / 1e9:.2f} GJ"
    if abs_j >= 1e6:
        return f"{j / 1e6:.2f} MJ"
    if abs_j >= 1e3:
        return f"{j / 1e3:.2f} kJ"
    return f"{j:.1f} J"


# ── Inline unit parsing ───────────────────────────────────────────────────────

_UNIT_CHARS = frozenset("ckfr")


def _typed_unit_to_kelvin(num: float, unit_char: str) -> float:
    """Convert a number in an explicitly typed unit (C/K/F/R) to Kelvin."""
    u = unit_char.lower()
    if u == "c":
        return num + 273.15
    if u == "k":
        return num
    if u == "f":
        return (num - 32.0) * 5.0 / 9.0 + 273.15
    return num * 5.0 / 9.0  # Rankine


class TempSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that accepts typed unit shortcuts: 100C, 100K, 100F, 100R.

    The typed unit is converted to the active display unit on commit.
    Plain numbers (no trailing letter) behave identically to QDoubleSpinBox.
    """

    def validate(self, text: str, pos: int):
        sfx   = self.suffix()
        inner = text[: -len(sfx)].rstrip() if (sfx and text.endswith(sfx)) else text.rstrip()
        if inner and inner[-1].lower() in _UNIT_CHARS:
            num_part = inner[:-1].strip()
            if num_part in ("", "-", "+"):
                return QValidator.State.Intermediate, text, pos
            try:
                float(num_part)
                return QValidator.State.Acceptable, text, pos
            except ValueError:
                pass
        return super().validate(text, pos)

    def valueFromText(self, text: str) -> float:
        sfx   = self.suffix()
        inner = text[: -len(sfx)].rstrip() if (sfx and text.endswith(sfx)) else text.rstrip()
        if inner and inner[-1].lower() in _UNIT_CHARS:
            try:
                num = float(inner[:-1].strip())
                k   = _typed_unit_to_kelvin(num, inner[-1])
                return to_display(k)
            except ValueError:
                pass
        return super().valueFromText(text)
