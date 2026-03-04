from __future__ import annotations

from enum import Enum


class Unit(str, Enum):
    CELSIUS    = "°C"
    KELVIN     = "K"
    FAHRENHEIT = "°F"


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
    return (k - 273.15) * 9.0 / 5.0 + 32.0  # Fahrenheit


def from_display(v: float) -> float:
    """Convert a displayed value back to Kelvin."""
    if _active == Unit.CELSIUS:
        return v + 273.15
    if _active == Unit.KELVIN:
        return v
    return (v - 32.0) * 5.0 / 9.0 + 273.15  # from Fahrenheit


def suffix() -> str:
    return _active.value


def spinbox_range() -> tuple[float, float]:
    """(min, max) in the current display unit."""
    if _active == Unit.CELSIUS:
        return -273.15, 10000.0
    if _active == Unit.KELVIN:
        return 0.0, 10273.15
    return -459.67, 18032.0  # Fahrenheit
