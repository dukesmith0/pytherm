from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from src.ui.temp_plot_panel import _PlotCanvas, _SERIES_COLORS


class PlotViewerDialog(QDialog):
    """Non-modal dialog for viewing saved .pythermplot files (read-only)."""

    def __init__(self, data: dict, title: str = "Plot Viewer", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 400)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        series_names = list(data.get("series", {}).keys())
        info = QLabel(f"{len(series_names)} series, read-only")
        info.setStyleSheet("color: #888; font-size: 10px;")
        bar.addWidget(info)
        bar.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(60)
        close_btn.clicked.connect(self.close)
        bar.addWidget(close_btn)
        layout.addLayout(bar)

        self._canvas = _PlotCanvas()
        layout.addWidget(self._canvas, stretch=1)

        self._load_data(data)

    def _load_data(self, data: dict) -> None:
        series = data.get("series", {})
        # Set max_points to actual data size so nothing is truncated
        max_pts = max((len(pts) for pts in series.values()), default=500)
        self._canvas.set_max_points(max(max_pts, 500))
        names = list(series.keys())
        self._canvas.set_series(names)
        for name, points in series.items():
            for t, T_k in points:
                self._canvas.add_point(name, t, T_k)
        self._canvas.update()


def load_pythermplot(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "series" not in data:
        raise ValueError("Invalid .pythermplot file: missing 'series' key")
    return data
