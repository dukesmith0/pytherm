from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from src.rendering import units as _units
from src.simulation.cell import Cell


def _tc():
    """Theme-aware tooltip colors."""
    p = QApplication.instance().palette()
    is_dark = p.window().color().lightnessF() < 0.5
    if is_dark:
        return {"bg": "#252525", "border": "#555", "name": "#eee",
                "pos": "#b0b0b0", "detail": "#c0c0c0"}
    return {"bg": "#f8f8f8", "border": "#bbb", "name": "#1e1e1e",
            "pos": "#555", "detail": "#333"}


class CellTooltip(QWidget):
    """Frameless floating tooltip that follows the cursor, showing cell info."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        c = _tc()
        self.setStyleSheet(
            f"CellTooltip {{ background-color: {c['bg']}; border: 1px solid {c['border']}; border-radius: 4px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._name = QLabel()
        self._name.setStyleSheet(f"font-weight: bold; color: {c['name']}; font-size: 12px;")
        layout.addWidget(self._name)

        self._pos    = QLabel()
        self._pos.setStyleSheet(f"color: {c['pos']}; font-size: 10px;")
        layout.addWidget(self._pos)

        self._k      = QLabel()
        self._alpha  = QLabel()
        self._temp   = QLabel()
        self._energy = QLabel()
        self._tau    = QLabel()
        self._resist = QLabel()
        self._flux_info = QLabel()
        for lbl in (self._k, self._alpha, self._temp, self._energy,
                    self._tau, self._resist, self._flux_info):
            lbl.setStyleSheet(f"color: {c['detail']}; font-size: 11px;")
            layout.addWidget(lbl)

    def update_cell(self, cell: Cell, dx_m: float, ambient_k: float,
                    row: int | None = None, col: int | None = None) -> None:
        """Refresh the displayed values for the given cell."""
        mat = cell.material
        self._name.setText(mat.name)
        if row is not None and col is not None:
            self._pos.setText(f"row {row}, col {col}")
            self._pos.setVisible(True)
        else:
            self._pos.setVisible(False)
        self._k.setText(f"k  =  {mat.k} W/(m·K)")
        self._alpha.setText(f"α  =  {mat.alpha:.3e} m²/s")
        self._temp.setText(f"T  =  {_units.to_display(cell.temperature):.1f} {_units.suffix()}")

        rho_cp = mat.rho * mat.cp
        if rho_cp > 0 and dx_m > 0:
            delta_e = rho_cp * (cell.temperature - ambient_k) * dx_m ** 2
            self._energy.setText(f"ΔE =  {_units.fmt_energy(delta_e)}")
            self._energy.setVisible(True)
        else:
            self._energy.setVisible(False)

        if rho_cp > 0 and dx_m > 0 and mat.k > 0:
            tau = rho_cp * dx_m ** 2 / mat.k
            self._tau.setText(f"\u03c4  =  {tau:.3g} s")
            self._tau.setVisible(True)
            self._resist.setText(f"R  =  {dx_m / mat.k:.4g} K\u00b7m\u00b2/W")
            self._resist.setVisible(True)
        else:
            self._tau.setVisible(False)
            self._resist.setVisible(False)

        if cell.is_flux:
            unit = "W/m\u00b3" if cell.is_volumetric_flux else "W/m\u00b2"
            sign = "+" if cell.flux_q >= 0 else ""
            self._flux_info.setText(f"q  =  {sign}{cell.flux_q:.2f} {unit}")
            self._flux_info.setVisible(True)
        else:
            self._flux_info.setVisible(False)

        self.adjustSize()

    def move_near(self, global_pos: QPoint) -> None:
        """Position the tooltip near the cursor, nudging away from screen edges."""
        ox, oy = 16, 16
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        sg = screen.geometry()
        x = global_pos.x() + ox
        y = global_pos.y() + oy
        w, h = self.width(), self.height()
        if x + w > sg.right():
            x = global_pos.x() - w - ox
        if y + h > sg.bottom():
            y = global_pos.y() - h - oy
        self.move(x, y)
