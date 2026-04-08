"""Tests for src.simulation.step_history.StepHistory."""
from __future__ import annotations

import numpy as np
from src.simulation.step_history import StepHistory


def test_push_and_back():
    sh = StepHistory(max_size=5)
    sh.push(np.full((3, 3), 300.0))
    sh.push(np.full((3, 3), 350.0))
    assert sh.at_present
    snap = sh.back()
    assert snap is not None
    assert not sh.at_present


def test_forward_returns():
    sh = StepHistory(max_size=5)
    sh.push(np.full((3, 3), 300.0))
    sh.push(np.full((3, 3), 350.0))
    sh.back()
    sh.back()
    snap = sh.forward()
    assert snap is not None


def test_return_to_present():
    sh = StepHistory(max_size=5)
    sh.push(np.full((3, 3), 300.0))
    sh.push(np.full((3, 3), 350.0))
    sh.back()
    snap = sh.return_to_present()
    assert snap is not None
    assert np.allclose(snap, 350.0)
    assert sh.at_present


def test_clear():
    sh = StepHistory(max_size=5)
    sh.push(np.full((2, 2), 300.0))
    sh.clear()
    assert sh.total == 0
    assert sh.at_present
    assert sh.back() is None


def test_max_size_limits():
    sh = StepHistory(max_size=3)
    for i in range(10):
        sh.push(np.full((2, 2), float(i)))
    assert sh.total == 3


def test_position_tracks():
    sh = StepHistory(max_size=10)
    for i in range(5):
        sh.push(np.full((2, 2), float(i)))
    assert sh.position == 5
    sh.back()
    assert sh.position == 4
    sh.back()
    assert sh.position == 3


def test_set_max_size_trims():
    sh = StepHistory(max_size=10)
    for i in range(10):
        sh.push(np.full((2, 2), float(i)))
    sh.set_max_size(3)
    assert sh.total == 3
    assert sh.at_present


def test_push_after_browsing():
    sh = StepHistory(max_size=5)
    sh.push(np.full((2, 2), 300.0))
    sh.push(np.full((2, 2), 350.0))
    sh.back()
    assert not sh.at_present
    sh.push(np.full((2, 2), 400.0))
    assert sh.at_present
