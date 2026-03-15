from __future__ import annotations

from collections import deque

import numpy as np


class StepHistory:
    """Circular buffer of temperature snapshots for step-by-step browsing.

    push() records a snapshot after each sim tick.
    back()/forward() navigate. at_present is True when viewing the latest.
    Each entry stores (T_array, sim_time).
    """

    def __init__(self, max_size: int = 20) -> None:
        self._max_size = max_size
        self._snapshots: deque[tuple[np.ndarray, float]] = deque(maxlen=max_size)
        self._index: int = -1  # -1 = at present (past end of buffer)

    @property
    def at_present(self) -> bool:
        return self._index < 0 or len(self._snapshots) == 0

    @property
    def position(self) -> int:
        if self.at_present:
            return len(self._snapshots)
        return self._index + 1

    @property
    def total(self) -> int:
        return len(self._snapshots)

    def set_max_size(self, n: int) -> None:
        self._max_size = n
        old = list(self._snapshots)[-n:]
        self._snapshots = deque(old, maxlen=n)
        self._index = -1

    def push(self, T: np.ndarray, sim_time: float = 0.0) -> None:
        self._snapshots.append((T.copy(), sim_time))
        self._index = -1  # always return to present on new data

    @property
    def current_time(self) -> float | None:
        if self._index < 0 or len(self._snapshots) == 0:
            return None
        return self._snapshots[self._index][1]

    def back(self) -> np.ndarray | None:
        if len(self._snapshots) == 0:
            return None
        if self._index < 0:
            self._index = len(self._snapshots) - 1
        if self._index > 0:
            self._index -= 1
            return self._snapshots[self._index][0].copy()
        return self._snapshots[0][0].copy()

    def forward(self) -> np.ndarray | None:
        if len(self._snapshots) == 0 or self._index < 0:
            return None
        if self._index < len(self._snapshots) - 1:
            self._index += 1
            return self._snapshots[self._index][0].copy()
        # Reached the end -- return to present
        self._index = -1
        return None

    def return_to_present(self) -> np.ndarray | None:
        if self._index < 0 or len(self._snapshots) == 0:
            return None
        self._index = -1
        return self._snapshots[-1][0].copy()

    def clear(self) -> None:
        self._snapshots.clear()
        self._index = -1
