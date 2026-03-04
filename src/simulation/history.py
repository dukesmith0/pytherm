from __future__ import annotations

from src.simulation.grid import Grid
from src.models.material import Material

# Type alias: a snapshot is a 2-D list indexed [row][col] of (material, temp, is_fixed, fixed_temp)
_CellTuple = tuple[Material, float, bool, float]
_Snapshot  = list[list[_CellTuple]]


class GridHistory:
    """Fixed-depth undo/redo stack for grid cell state.

    Call push() BEFORE making a change to capture the current state.
    Then call undo() / redo() to restore.
    """

    MAX_SNAPSHOTS = 50

    def __init__(self) -> None:
        self._undo: list[_Snapshot] = []
        self._redo: list[_Snapshot] = []

    # --- Public API ---

    def push(self, grid: Grid) -> None:
        """Capture grid's current state as a new undo step."""
        self._undo.append(self._snap(grid))
        if len(self._undo) > self.MAX_SNAPSHOTS:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, grid: Grid) -> bool:
        """Restore previous state into grid. Returns True if a step was available."""
        if not self._undo:
            return False
        self._redo.append(self._snap(grid))
        self._restore(grid, self._undo.pop())
        return True

    def redo(self, grid: Grid) -> bool:
        """Re-apply undone state into grid. Returns True if a step was available."""
        if not self._redo:
            return False
        self._undo.append(self._snap(grid))
        self._restore(grid, self._redo.pop())
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    # --- Internals ---

    @staticmethod
    def _snap(grid: Grid) -> _Snapshot:
        return [
            [
                (cell.material, cell.temperature, cell.is_fixed, cell.fixed_temp)
                for cell in row
            ]
            for row in grid._cells
        ]

    @staticmethod
    def _restore(grid: Grid, snapshot: _Snapshot) -> None:
        for r, row in enumerate(snapshot):
            for c, (mat, temp, is_fixed, fixed_temp) in enumerate(row):
                grid.set_cell(r, c,
                              material=mat,
                              temperature=temp,
                              is_fixed=is_fixed,
                              fixed_temp=fixed_temp)
