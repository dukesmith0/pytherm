from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsScene

from src.rendering import units as _units
from src.rendering.heatmap_renderer import heatmap_color, text_color_for_bg
from src.rendering.material_renderer import cell_color, draw_lock_icon
from src.simulation.grid import Grid

# Scene coordinate size of each cell at 1:1 zoom.
# Zoom is handled by QGraphicsView's transform — the scene itself never changes scale.
CELL_PX = 32

# Minimum on-screen cell size (pixels) before temperature labels are drawn in heatmap mode.
_LABEL_THRESHOLD_PX = 30


class GridScene(QGraphicsScene):
    def __init__(self, grid: Grid) -> None:
        super().__init__()
        self._grid = grid
        self.show_grid_lines = True
        self._preview_rect: tuple[int, int, int, int] | None = None   # (r1,c1,r2,c2)
        self._preview_cells: list[tuple[int, int]] | None = None       # Bresenham line
        self._selected_cell: tuple[int, int] | None = None
        self._multi_selection: set[tuple[int, int]] = set()

        # Heatmap state
        self._view_mode: str = "material"   # "material" | "heatmap"
        self._heatmap_auto: bool = True
        self._heatmap_t_min: float = 273.15  # 0 °C in K
        self._heatmap_t_max: float = 373.15  # 100 °C in K

        # Anchored auto-scale: bounds only expand, never contract.
        # None = not yet initialised for this simulation run.
        self._auto_t_min: float | None = None
        self._auto_t_max: float | None = None

        self._show_abbr: bool = False

        # Per-frame bounds cache: computed once in drawBackground, reused in drawForeground.
        self._frame_bounds: tuple[float, float] = (273.15, 373.15)

        # Fixed-cell position cache: None = dirty, rebuilt lazily in drawForeground.
        self._fixed_cells: set[tuple[int, int]] | None = None

        self._sync_scene_rect()

    def _sync_scene_rect(self) -> None:
        self.setSceneRect(0, 0, self._grid.cols * CELL_PX, self._grid.rows * CELL_PX)

    # --- Public API ---

    def set_grid(self, grid: Grid) -> None:
        self._grid = grid
        self._preview_rect = None
        self._preview_cells = None
        self._selected_cell = None
        self._multi_selection = set()
        self._auto_t_min = None
        self._auto_t_max = None
        self._fixed_cells = None
        self._sync_scene_rect()
        self.update()

    def invalidate_fixed_cells(self) -> None:
        """Mark the fixed-cell cache dirty so it rebuilds next frame."""
        self._fixed_cells = None

    def reset_auto_heatmap_bounds(self) -> None:
        """Clear the anchored auto-scale bounds so they re-initialise on the next frame."""
        self._auto_t_min = None
        self._auto_t_max = None

    def refresh(self) -> None:
        self.update()

    def set_preview_rect(self, r1: int, c1: int, r2: int, c2: int) -> None:
        self._preview_rect = (min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2))
        self._preview_cells = None
        self.update()

    def set_line_preview(self, cells: list[tuple[int, int]]) -> None:
        self._preview_cells = list(cells)
        self._preview_rect = None
        self.update()

    def clear_preview(self) -> None:
        changed = self._preview_rect is not None or self._preview_cells is not None
        self._preview_rect = None
        self._preview_cells = None
        if changed:
            self.update()

    def set_selected_cell(self, row: int, col: int) -> None:
        self._selected_cell = (row, col)
        self.update()

    def clear_selected_cell(self) -> None:
        if self._selected_cell is not None:
            self._selected_cell = None
            self.update()

    def set_multi_selection(self, cells: set[tuple[int, int]]) -> None:
        self._multi_selection = set(cells)
        self.update()

    def set_view_mode(self, mode: str) -> None:
        self._view_mode = mode
        self.update()

    def set_heatmap_auto(self, auto: bool) -> None:
        self._heatmap_auto = auto
        self.update()

    def set_heatmap_range(self, t_min_k: float, t_max_k: float) -> None:
        self._heatmap_t_min = t_min_k
        self._heatmap_t_max = t_max_k
        if not self._heatmap_auto:
            self.update()

    def set_show_abbr(self, show: bool) -> None:
        self._show_abbr = show
        self.update()

    # --- Rendering ---

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor(25, 25, 25))

        g  = self._grid
        cp = CELL_PX

        # Viewport culling: only iterate cells visible in the dirty rect.
        c0 = max(0, int(rect.x() / cp))
        c1 = min(g.cols, int((rect.x() + rect.width()) / cp) + 1)
        r0 = max(0, int(rect.y() / cp))
        r1 = min(g.rows, int((rect.y() + rect.height()) / cp) + 1)

        if self._view_mode == "heatmap":
            # Compute bounds once per frame; reused by drawForeground helpers.
            self._frame_bounds = self._heatmap_bounds()
            self._draw_heatmap(painter, g, cp, r0, r1, c0, c1)
        else:
            for r in range(r0, r1):
                for c in range(c0, c1):
                    painter.fillRect(c * cp, r * cp, cp, cp, cell_color(g.cell(r, c)))

        if self.show_grid_lines:
            pen = QPen(QColor(50, 50, 50))
            pen.setCosmetic(True)
            painter.setPen(pen)
            for r in range(r0, r1 + 1):
                painter.drawLine(c0 * cp, r * cp, c1 * cp, r * cp)
            for c in range(c0, c1 + 1):
                painter.drawLine(c * cp, r0 * cp, c * cp, r1 * cp)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        cp   = CELL_PX
        g    = self._grid
        zoom = painter.deviceTransform().m11()

        # Viewport culling bounds for foreground elements
        c0 = max(0, int(rect.x() / cp))
        c1 = min(g.cols, int((rect.x() + rect.width()) / cp) + 1)
        r0 = max(0, int(rect.y() / cp))
        r1 = min(g.rows, int((rect.y() + rect.height()) / cp) + 1)

        # Material abbreviations — bottom-left corner of each non-vacuum cell
        if self._show_abbr:
            self._draw_abbr(painter, g, cp, zoom, r0, r1, c0, c1)

        # Multi-selection highlight (blue overlay, drawn below previews)
        if self._multi_selection:
            for r, c in self._multi_selection:
                if r0 <= r < r1 and c0 <= c < c1:
                    painter.fillRect(c * cp, r * cp, cp, cp, QColor(80, 140, 220, 55))
            sel_pen = QPen(QColor(100, 160, 255))
            sel_pen.setCosmetic(True)
            sel_pen.setWidth(1)
            painter.setPen(sel_pen)
            for r, c in self._multi_selection:
                if r0 <= r < r1 and c0 <= c < c1:
                    painter.drawRect(c * cp, r * cp, cp - 1, cp - 1)

        # Shift-drag rectangle preview — semi-transparent teal fill with border
        if self._preview_rect is not None:
            r1p, c1p, r2p, c2p = self._preview_rect
            x, y = c1p * cp, r1p * cp
            w, h = (c2p - c1p + 1) * cp, (r2p - r1p + 1) * cp
            painter.fillRect(x, y, w, h, QColor(0, 150, 136, 70))
            pen = QPen(QColor(0, 200, 180))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(x, y, w - 1, h - 1)

        # Ctrl-drag Bresenham line preview — per-cell teal fill with border
        if self._preview_cells is not None:
            pen = QPen(QColor(0, 200, 180))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            for r, c in self._preview_cells:
                painter.fillRect(c * cp, r * cp, cp, cp, QColor(0, 150, 136, 70))
                painter.drawRect(c * cp + 1, r * cp + 1, cp - 2, cp - 2)

        # Lock icons on fixed-temperature cells (cached set, lazily rebuilt)
        if self._fixed_cells is None:
            self._fixed_cells = {
                (r, c)
                for r in range(g.rows)
                for c in range(g.cols)
                if g.cell(r, c).is_fixed
            }
        for r, c in self._fixed_cells:
            if r0 <= r < r1 and c0 <= c < c1:
                draw_lock_icon(painter, c * cp, r * cp, cp)

        # Selected cell — white border highlight (single-cell select)
        if self._selected_cell is not None:
            r, c = self._selected_cell
            x, y = c * cp, r * cp
            pen = QPen(QColor(255, 255, 255))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(x + 1, y + 1, cp - 2, cp - 2)

        # Grid coordinate overlay — row/col numbers at edges when zoomed in
        self._draw_grid_coords(painter, g, cp, zoom)

        # Color scale legend — bottom-right corner, heatmap mode only
        if self._view_mode == "heatmap":
            self._draw_color_legend(painter)

    # --- Heatmap helpers ---

    # Background color used outside the grid and for vacuum cells in heatmap mode.
    _BG_COLOR = QColor(25, 25, 25)

    @staticmethod
    def _display_temp(cell) -> float:
        """Temperature to use for heatmap rendering — honours fixed-source cells."""
        return cell.fixed_temp if cell.is_fixed else cell.temperature

    def _heatmap_bounds(self) -> tuple[float, float]:
        if self._heatmap_auto:
            temps = [
                self._display_temp(self._grid.cell(r, c))
                for r in range(self._grid.rows)
                for c in range(self._grid.cols)
                if not self._grid.cell(r, c).material.is_vacuum
            ]
            if not temps:
                return 273.15, 373.15
            t_min_now, t_max_now = min(temps), max(temps)

            if self._auto_t_min is None:
                self._auto_t_min = t_min_now
                self._auto_t_max = t_max_now
            else:
                self._auto_t_min = min(self._auto_t_min, t_min_now)
                self._auto_t_max = max(self._auto_t_max, t_max_now)

            t_min, t_max = self._auto_t_min, self._auto_t_max
            if t_max - t_min < 0.1:
                t_max = t_min + 0.1
            return t_min, t_max
        return self._heatmap_t_min, self._heatmap_t_max

    def _draw_abbr(self, painter: QPainter, g: Grid, cp: int, zoom: float,
                   r0: int, r1: int, c0: int, c1: int) -> None:
        if cp * zoom < _LABEL_THRESHOLD_PX:
            return

        font = QFont()
        font.setPixelSize(max(7, int(cp * 0.22)))
        painter.setFont(font)

        t_min, t_max = self._frame_bounds
        pad = max(2, int(cp * 0.08))

        for r in range(r0, r1):
            for c in range(c0, c1):
                cell = g.cell(r, c)
                abbr = cell.material.abbr
                if not abbr or cell.material.is_vacuum:
                    continue
                if self._view_mode == "heatmap":
                    bg = heatmap_color(self._display_temp(cell), t_min, t_max)
                else:
                    bg = cell_color(cell)
                painter.setPen(text_color_for_bg(bg))
                painter.drawText(
                    QRectF(c * cp + pad, r * cp, cp - pad * 2, cp - pad),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    abbr,
                )

    def _draw_heatmap(self, painter: QPainter, g: Grid, cp: int,
                      r0: int, r1: int, c0: int, c1: int) -> None:
        t_min, t_max = self._frame_bounds

        for r in range(r0, r1):
            for c in range(c0, c1):
                cell = g.cell(r, c)
                if cell.material.is_vacuum:
                    color = self._BG_COLOR
                else:
                    color = heatmap_color(self._display_temp(cell), t_min, t_max)
                painter.fillRect(c * cp, r * cp, cp, cp, color)

        zoom = painter.deviceTransform().m11()
        if cp * zoom >= _LABEL_THRESHOLD_PX:
            font = QFont()
            font.setPixelSize(max(8, int(cp * 0.32)))
            painter.setFont(font)

            for r in range(r0, r1):
                for c in range(c0, c1):
                    cell = g.cell(r, c)
                    if cell.material.is_vacuum:
                        continue
                    t  = self._display_temp(cell)
                    bg = heatmap_color(t, t_min, t_max)
                    painter.setPen(text_color_for_bg(bg))
                    painter.drawText(
                        QRectF(c * cp, r * cp, cp, cp),
                        Qt.AlignmentFlag.AlignCenter,
                        f"{_units.to_display(t):.0f}{_units.suffix()}",
                    )

    def _draw_grid_coords(self, painter: QPainter, g: Grid, cp: int, zoom: float) -> None:
        """Draw row/col indices along the grid edges when zoomed in enough."""
        if cp * zoom < 24:
            return
        font = QFont()
        font.setPixelSize(max(7, int(cp * 0.2)))
        painter.setFont(font)
        painter.setPen(QColor(130, 130, 130))
        half = cp // 2
        for c in range(g.cols):
            painter.drawText(QRectF(c * cp, -half, cp, half),
                             Qt.AlignmentFlag.AlignCenter, str(c))
        for r in range(g.rows):
            painter.drawText(QRectF(-half, r * cp, half, cp),
                             Qt.AlignmentFlag.AlignCenter, str(r))

    def _draw_color_legend(self, painter: QPainter) -> None:
        """Draw a vertical color scale bar (hot=top, cold=bottom) in the viewport corner."""
        t_min, t_max = self._frame_bounds

        painter.save()
        painter.resetTransform()

        device = painter.device()
        vp_w   = device.width()
        vp_h   = device.height()

        BAR_W = 16
        bar_h = min(160, vp_h - 80)
        if bar_h < 20:
            painter.restore()
            return

        x = vp_w - BAR_W - 52
        y = vp_h - bar_h - 20

        grad = QLinearGradient(x, y, x, y + bar_h)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            t = t_max - frac * (t_max - t_min)
            grad.setColorAt(frac, heatmap_color(t, t_min, t_max))

        painter.fillRect(x, y, BAR_W, bar_h, QBrush(grad))

        border_pen = QPen(QColor(100, 100, 100))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawRect(x, y, BAR_W - 1, bar_h - 1)

        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QColor(200, 200, 200))

        suf = _units.suffix()
        painter.drawText(x + BAR_W + 4, y + 11,
                         f"{_units.to_display(t_max):.0f} {suf}")
        painter.drawText(x + BAR_W + 4, y + bar_h,
                         f"{_units.to_display(t_min):.0f} {suf}")

        painter.restore()
