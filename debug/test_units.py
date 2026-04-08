"""Tests for src.rendering.units temperature conversions."""
from __future__ import annotations

from src.rendering import units as u


def test_ckfr_round_trip():
    T_k = 373.15
    u.set_unit(u.Unit.CELSIUS);    assert abs(u.to_display(T_k) - 100.0) < 0.01
    u.set_unit(u.Unit.KELVIN);     assert abs(u.to_display(T_k) - 373.15) < 0.01
    u.set_unit(u.Unit.FAHRENHEIT); assert abs(u.to_display(T_k) - 212.0) < 0.01
    u.set_unit(u.Unit.RANKINE);    assert abs(u.to_display(T_k) - 671.67) < 0.1
    u.set_unit(u.Unit.CELSIUS)


def test_from_display_inverse():
    for unit in (u.Unit.CELSIUS, u.Unit.KELVIN, u.Unit.FAHRENHEIT, u.Unit.RANKINE):
        u.set_unit(unit)
        for T_k in (200.0, 293.15, 373.15, 1000.0):
            T_disp = u.to_display(T_k)
            T_back = u.from_display(T_disp)
            assert abs(T_back - T_k) < 0.01, f"{unit}: round-trip failed at {T_k} K"
    u.set_unit(u.Unit.CELSIUS)


def test_fmt_energy():
    from src.rendering.units import fmt_energy
    assert "J" in fmt_energy(50.0)
    assert "kJ" in fmt_energy(5000.0) or "J" in fmt_energy(5000.0)


def test_delta_celsius_kelvin_one_to_one():
    u.set_unit(u.Unit.CELSIUS)
    assert abs(u.delta_k_to_display(50.0) - 50.0) < 1e-9
    u.set_unit(u.Unit.KELVIN)
    assert abs(u.delta_k_to_display(50.0) - 50.0) < 1e-9
    u.set_unit(u.Unit.CELSIUS)


def test_delta_fahrenheit_scales():
    u.set_unit(u.Unit.FAHRENHEIT)
    assert abs(u.delta_k_to_display(50.0) - 90.0) < 1e-9
    u.set_unit(u.Unit.CELSIUS)


def test_delta_round_trip():
    for unit in (u.Unit.CELSIUS, u.Unit.KELVIN, u.Unit.FAHRENHEIT, u.Unit.RANKINE):
        u.set_unit(unit)
        dk = 50.0
        assert abs(u.delta_display_to_k(u.delta_k_to_display(dk)) - dk) < 1e-9
    u.set_unit(u.Unit.CELSIUS)


def test_typed_unit_to_kelvin():
    from src.rendering.units import _typed_unit_to_kelvin
    assert abs(_typed_unit_to_kelvin(20, "C") - 293.15) < 0.01
    assert abs(_typed_unit_to_kelvin(68, "F") - 293.15) < 0.01
    assert abs(_typed_unit_to_kelvin(293, "K") - 293.0) < 0.01
    assert abs(_typed_unit_to_kelvin(527.67, "R") - 293.15) < 0.01
