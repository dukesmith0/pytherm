"""Tests for Grid.resize()."""
from __future__ import annotations


def test_expand_top(make_grid):
    grid, reg = make_grid(4, 4)
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=400.0)
    vac = reg.get("vacuum")
    grid.resize(top=2, right=0, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows == 6 and grid.cols == 4
    assert grid.cell(0, 0).material.is_vacuum
    assert abs(grid.cell(0, 0).temperature - grid.ambient_temp_k) < 1e-9
    assert grid.cell(2, 0).material.id == "al6061"


def test_expand_bottom(make_grid):
    grid, reg = make_grid(4, 4)
    vac = reg.get("vacuum")
    grid.resize(top=0, right=0, bottom=3, left=0, vacuum_material=vac)
    assert grid.rows == 7 and grid.cols == 4


def test_expand_left(make_grid):
    grid, reg = make_grid(4, 4)
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al)
    vac = reg.get("vacuum")
    grid.resize(top=0, right=0, bottom=0, left=2, vacuum_material=vac)
    assert grid.rows == 4 and grid.cols == 6
    assert grid.cell(0, 2).material.id == "al6061"


def test_trim_top(make_grid):
    grid, reg = make_grid(6, 4)
    vac = reg.get("vacuum")
    grid.resize(top=-2, right=0, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows == 4 and grid.cols == 4


def test_trim_right(make_grid):
    grid, reg = make_grid(4, 6)
    vac = reg.get("vacuum")
    grid.resize(top=0, right=-3, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows == 4 and grid.cols == 3


def test_combined_expand_trim(make_grid):
    grid, reg = make_grid(4, 4)
    vac = reg.get("vacuum")
    grid.resize(top=2, right=-1, bottom=0, left=1, vacuum_material=vac)
    assert grid.rows == 6 and grid.cols == 4


def test_clamped_min_size(make_grid):
    grid, reg = make_grid(2, 2)
    vac = reg.get("vacuum")
    grid.resize(top=-100, right=-100, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows >= 1 and grid.cols >= 1


def test_preserves_cell_data(make_grid):
    grid, reg = make_grid(4, 4)
    al = reg.get("al6061")
    grid.set_cell(2, 2, material=al, temperature=500.0, is_fixed=True, fixed_temp=500.0)
    vac = reg.get("vacuum")
    grid.resize(top=1, right=0, bottom=0, left=0, vacuum_material=vac)
    c = grid.cell(3, 2)
    assert c.material.id == "al6061"
    assert abs(c.temperature - 500.0) < 1e-9
    assert c.is_fixed is True
