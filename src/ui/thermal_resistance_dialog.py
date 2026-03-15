from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from src.rendering import units as _units
from src.simulation.thermal_resistance import RthResult


class ThermalResistanceDialog(QDialog):
    """Displays thermal resistance calculation results."""

    def __init__(self, result: RthResult, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thermal Resistance Report")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        suf = _units.suffix()
        t_src = _units.to_display(result.t_source_avg_k)
        t_snk = _units.to_display(result.t_sink_avg_k)

        lines = [
            f"Source cells:     {result.n_source}",
            f"Sink cells:       {result.n_sink}",
            "",
            f"T_source (avg):   {t_src:.2f} {suf}",
            f"T_sink (avg):     {t_snk:.2f} {suf}",
            f"dT:               {result.dt_k:.4f} K",
            "",
            f"Q (heat flow):    {result.q_wpm:.4g} W/m",
            f"R_th:             {result.rth_kpwpm:.4g} K/(W/m)",
        ]
        text = "\n".join(lines)

        viewer = QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setFont(QFont("Courier New", 10))
        viewer.setPlainText(text)
        viewer.setMinimumHeight(180)
        layout.addWidget(viewer)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
        btn_row.addWidget(copy_btn)
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
