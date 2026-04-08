from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QPointF, QRect, QRectF
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsScene

from src.rendering import units as _units
from src.rendering.heatmap_renderer import heatmap_color, text_color_for_bg
from src.rendering.material_renderer import cell_color, draw_flame_icon, draw_lock_icon, draw_pin_icon
from src.simulation.grid import Grid

# Scene coordinate size of each cell at 1:1 zoom.
# Zoom is handled by QGraphicsView's transform -- the scene itself never changes scale.
CELL_PX = 32

# Minimum on-screen cell size (pixels) before temperature labels are drawn in heatmap mode.
_LABEL_THRESHOLD_PX = 30


class GridScene(QGraphicsScene):
    def __init__(self, grid: Grid) -> None:
        super().__init__()
        self._grid = grid
        self._dx_m: float = 0.01  # cell spacing in meters, updated by app.py
        self.show_grid_lines = True
        self._preview_rect: tuple[int, int, int, int] | None = None   # (r1,c1,r2,c2)
        self._preview_cells: list[tuple[int, int]] | None = None       # Bresenham line
        self._selected_cell: tuple[int, int] | None = None
        self._multi_selection: set[tuple[int, int]] = set()

        # Heatmap state
        self._view_mode: str = "material"   # "material" | "heatmap" | "flow"
        self._heatmap_auto: bool = True      # auto-init bounds from grid data
        self._scale_mode: str = "smart"      # "static" | "live" | "smart"
        self._heatmap_t_min: float = 273.15  # manual min (0 C in K)
        self._heatmap_t_max: float = 373.15  # manual max (100 C in K)

        # Anchored bounds for smart mode. None = not yet initialised.
        self._auto_t_min: float | None = None
        self._auto_t_max: float | None = None
        self._min_auto_range_k: float = 10.0  # minimum K span for auto heatmap scale

        self._show_abbr: bool = False
        self._show_label: bool = True
        self._show_delta: bool = False

        # Group label highlight: cells sharing a label with the currently selected cell.
        self._group_highlight: set[tuple[int, int]] = set()
        self._group_highlight_label: str = ""

        # Per-frame bounds cache: computed once in drawBackground, reused in drawForeground.
        self._frame_bounds: tuple[float, float] = (273.15, 373.15)

        # Fixed-cell, flux-cell, and protected-cell position caches: None = dirty, rebuilt lazily.
        self._fixed_cells: set[tuple[int, int]] | None = None
        self._flux_cells: set[tuple[int, int]] | None = None
        self._protected_cells: set[tuple[int, int]] | None = None

        # Non-vacuum cell list cache for heatmap bounds: None = dirty.
        self._nv_cells: list[tuple[int, int]] | None = None

        self._show_legend: bool = False
        self._mat_image: QImage | None = None  # cached material view image; None = dirty

        # Isotherm overlay
        self._isotherm_enabled: bool = False
        self._isotherm_interval_k: float = 50.0
        self._isotherm_color: QColor = QColor(230, 230, 230, 220)
        self._isotherm_line_width: int = 2

        # Flux view bounds (set per frame in _draw_flux_view)
        self._flow_bounds: tuple[float, float] = (0.0, 1.0)

        # Heat flow vector overlay
        self._show_heat_vectors: bool = False

        # Hotspot overlay
        self._hotspot_enabled: bool = False
        self._hotspot_threshold_k: float = math.nan

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
        self._flux_cells = None
        self._protected_cells = None
        self._nv_cells = None
        self._mat_image = None
        self._group_highlight = set()
        self._group_highlight_label = ""
        self._sync_scene_rect()
        self.update()

    def invalidate_fixed_cells(self) -> None:
        """Mark the fixed/flux/protected/nv-cell caches dirty so they rebuild next frame."""
        self._fixed_cells = None
        self._flux_cells = None
        self._protected_cells = None
        self._nv_cells = None
        self._mat_image = None

    @property
    def frame_bounds(self) -> tuple[float, float]:
        """Current heatmap temperature bounds (updated each frame in heatmap mode)."""
        return self._frame_bounds

    def set_show_legend(self, show: bool) -> None:
        """Show or hide the embedded legend (disable when LegendOverlay is active)."""
        self._show_legend = show
        self.update()

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
        self._auto_t_min = None
        self._auto_t_max = None
        self.update()

    def set_scale_mode(self, mode: str) -> None:
        self._scale_mode = mode
        self._auto_t_min = None
        self._auto_t_max = None
        self.update()

    def set_heatmap_range(self, t_min_k: float, t_max_k: float) -> None:
        self._heatmap_t_min = t_min_k
        self._heatmap_t_max = t_max_k
        self._auto_t_min = None
        self._auto_t_max = None
        self.update()

    def set_min_auto_range(self, range_k: float) -> None:
        self._min_auto_range_k = max(0.1, range_k)
        self.update()

    def set_show_abbr(self, show: bool) -> None:
        self._show_abbr = show
        self.update()

    def set_show_label(self, show: bool) -> None:
        self._show_label = show
        self.update()

    def set_show_heat_vectors(self, show: bool) -> None:
        self._show_heat_vectors = show
        self.update()

    def set_show_delta(self, show: bool) -> None:
        self._show_delta = show
        self.update()

    def set_group_highlight(self, cells: set[tuple[int, int]], label: str = "") -> None:
        self._group_highlight = cells
        self._group_highlight_label = label
        self.update()

    def set_isotherm(self, enabled: bool, interval_k: float) -> None:
        self._isotherm_enabled = enabled
        self._isotherm_interval_k = max(0.01, interval_k)
        self.update()

    @property
    def legend_bounds(self) -> tuple[float, float]:
        """Bounds for the legend overlay -- temperature or flux depending on view mode."""
        if self._view_mode == "flow":
            return self._flow_bounds
        return self.frame_bounds

    def set_isotherm_color(self, color: QColor) -> None:
        self._isotherm_color = color

    def set_isotherm_line_width(self, width: int) -> None:
        self._isotherm_line_width = max(1, min(5, width))
        self.update()

    def set_hotspot_threshold(self, threshold_k: float) -> None:
        self._hotspot_enabled = not math.isnan(threshold_k)
        self._hotspot_threshold_k = threshold_k
        self.update()

    @property
    def hotspot_count(self) -> int:
        """Number of non-vacuum cells currently above the hotspot threshold."""
        if not self._hotspot_enabled or math.isnan(self._hotspot_threshold_k):
            return 0
        g = self._grid
        count = 0
        for r in range(g.rows):
            for c in range(g.cols):
                cell = g.cell(r, c)
                if not cell.material.is_vacuum and self._display_temp(cell) > self._hotspot_threshold_k:
                    count += 1
        return count

    # --- Rendering ---

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self._BG_COLOR)

        g  = self._grid
        cp = CELL_PX

        # Viewport culling: only iterate cells visible in the dirty rect.
        c0 = max(0, int(rect.x() / cp))
        c1 = min(g.cols, int((rect.x() + rect.width()) / cp) + 1)
        r0 = max(0, int(rect.y() / cp))
        r1 = min(g.rows, int((rect.y() + rect.height()) / cp) + 1)

        if self._view_mode == "heatmap":
            self._frame_bounds = self._heatmap_bounds()
            self._draw_heatmap(painter, g, cp, r0, r1, c0, c1)
        elif self._view_mode == "flow":
            self._frame_bounds = self._heatmap_bounds()
            self._draw_flux_view(painter, g, cp, r0, r1, c0, c1)
        else:
            if self._mat_image is None:
                self._mat_image = self._build_mat_image()
            src = QRect(c0 * cp, r0 * cp, (c1 - c0) * cp, (r1 - r0) * cp)
            painter.drawImage(src, self._mat_image, src)

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

        # Cell labels and material abbreviations (labels always shown; abbr only when toggled)
        self._draw_cell_text(painter, g, cp, zoom, r0, r1, c0, c1)

        # Group label highlight (orange overlay for cells sharing a label with selected cell)
        if self._group_highlight:
            for r, c in self._group_highlight:
                if r0 <= r < r1 and c0 <= c < c1:
                    painter.fillRect(c * cp, r * cp, cp, cp, QColor(255, 140, 0, 45))
            gh_pen = QPen(QColor(255, 165, 50))
            gh_pen.setCosmetic(True)
            gh_pen.setWidth(1)
            painter.setPen(gh_pen)
            for r, c in self._group_highlight:
                if r0 <= r < r1 and c0 <= c < c1:
                    painter.drawRect(c * cp, r * cp, cp - 1, cp - 1)
            if self._group_highlight_label:
                grows = [r for r, c in self._group_highlight]
                gcols = [c for r, c in self._group_highlight]
                r_min = min(grows)
                c_min, c_max = min(gcols), max(gcols)
                badge_w = (c_max - c_min + 1) * cp
                badge_h = 16
                badge_x = c_min * cp
                badge_y = max(0, r_min * cp - badge_h - 2)
                painter.fillRect(badge_x, badge_y, badge_w, badge_h, QColor(255, 140, 0, 210))
                badge_font = QFont()
                badge_font.setPixelSize(10)
                badge_font.setBold(True)
                painter.setFont(badge_font)
                painter.setPen(QColor(20, 20, 20))
                painter.drawText(
                    QRectF(badge_x, badge_y, badge_w, badge_h),
                    Qt.AlignmentFlag.AlignCenter,
                    self._group_highlight_label,
                )

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

        # Shift-drag rectangle preview -- semi-transparent teal fill with border
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

        # Ctrl-drag Bresenham line preview -- per-cell teal fill with border
        if self._preview_cells is not None:
            pen = QPen(QColor(0, 200, 180))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            for r, c in self._preview_cells:
                painter.fillRect(c * cp, r * cp, cp, cp, QColor(0, 150, 136, 70))
                painter.drawRect(c * cp + 1, r * cp + 1, cp - 2, cp - 2)

        # Pin icons on fixed-T cells, flame on flux cells, lock on protected cells (cached, lazily rebuilt)
        if self._fixed_cells is None:
            self._fixed_cells = set()
            self._flux_cells = set()
            self._protected_cells = set()
            for _r in range(g.rows):
                for _c in range(g.cols):
                    cell = g.cell(_r, _c)
                    if cell.is_fixed:
                        self._fixed_cells.add((_r, _c))
                    if cell.is_flux:
                        self._flux_cells.add((_r, _c))
                    if cell.protected:
                        self._protected_cells.add((_r, _c))
        icon_w = max(8, cp // 4) + 2  # icon width + padding, matches icon sizing
        all_icon_cells = self._fixed_cells | self._flux_cells | self._protected_cells
        for r, c in all_icon_cells:
            if r0 <= r < r1 and c0 <= c < c1:
                off = 0
                if (r, c) in self._fixed_cells:
                    draw_pin_icon(painter, c * cp, r * cp, cp, x_offset=off)
                    off += icon_w
                if (r, c) in self._flux_cells:
                    draw_flame_icon(painter, c * cp, r * cp, cp, x_offset=off)
                    off += icon_w
                if (r, c) in self._protected_cells:
                    draw_lock_icon(painter, c * cp, r * cp, cp, x_offset=off)

        # Selected cell -- white border highlight (single-cell select)
        if self._selected_cell is not None:
            r, c = self._selected_cell
            x, y = c * cp, r * cp
            pen = QPen(QColor(255, 255, 255))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(x + 1, y + 1, cp - 2, cp - 2)

        # Grid coordinate overlay -- row/col numbers at edges when zoomed in
        self._draw_grid_coords(painter, g, cp, zoom)

        # Hotspot highlight -- semi-transparent red on cells above threshold (all views)
        if self._hotspot_enabled and not math.isnan(self._hotspot_threshold_k):
            self._draw_hotspot(painter, g, cp, r0, r1, c0, c1)

        # Heat flow vector arrows -- heatmap and flux modes
        if self._view_mode in ("heatmap", "flow") and self._show_heat_vectors:
            self._draw_heat_vectors(painter, g, cp, zoom, r0, r1, c0, c1)

        # Isotherm lines -- heatmap and flux modes
        if self._view_mode in ("heatmap", "flow") and self._isotherm_enabled:
            self._draw_isotherms(painter, g, cp, r0, r1, c0, c1)

        # Color scale legend -- bottom-right corner, heatmap mode only
        if self._view_mode in ("heatmap", "flow") and self._show_legend:
            self._draw_color_legend(painter)

    # --- Heatmap helpers ---

    # Background color used outside the grid and for vacuum cells in heatmap mode.
    _BG_COLOR = QColor(25, 25, 25)
    _BG_COLOR_DARK = QColor(25, 25, 25)
    _BG_COLOR_LIGHT = QColor(240, 240, 240)

    def set_theme(self, theme: str) -> None:
        """Update colors for the current theme."""
        if theme == "light":
            self._BG_COLOR = self._BG_COLOR_LIGHT
        else:
            self._BG_COLOR = self._BG_COLOR_DARK
        self._mat_image = None  # force rebuild
        self.invalidate()

    @staticmethod
    def _display_temp(cell) -> float:
        """Temperature to use for heatmap rendering -- honours fixed-source cells."""
        return cell.fixed_temp if cell.is_fixed else cell.temperature

    def _heatmap_bounds(self) -> tuple[float, float]:
        # Determine starting bounds: auto-init from grid, or manual spinbox values.
        if self._heatmap_auto:
            if self._nv_cells is None:
                self._nv_cells = [
                    (r, c)
                    for r in range(self._grid.rows)
                    for c in range(self._grid.cols)
                    if not self._grid.cell(r, c).material.is_vacuum
                ]
            temps = [self._display_temp(self._grid.cell(r, c)) for r, c in self._nv_cells]
            if not temps:
                return 273.15, 373.15
            t_min_now, t_max_now = min(temps), max(temps)
        else:
            # Manual: starting bounds from spinbox values
            if self._nv_cells is None:
                self._nv_cells = [
                    (r, c)
                    for r in range(self._grid.rows)
                    for c in range(self._grid.cols)
                    if not self._grid.cell(r, c).material.is_vacuum
                ]
            temps = [self._display_temp(self._grid.cell(r, c)) for r, c in self._nv_cells]
            t_min_now = min(temps) if temps else self._heatmap_t_min
            t_max_now = max(temps) if temps else self._heatmap_t_max

        mode = self._scale_mode

        if mode == "static":
            # Bounds stay at starting values (auto-init or manual).
            if self._auto_t_min is None:
                if self._heatmap_auto:
                    self._auto_t_min = t_min_now
                    self._auto_t_max = t_max_now
                else:
                    self._auto_t_min = self._heatmap_t_min
                    self._auto_t_max = self._heatmap_t_max
            return self._apply_min_range(self._auto_t_min, self._auto_t_max)

        elif mode == "live":
            # Bounds track current grid min/max every frame.
            return self._apply_min_range(t_min_now, t_max_now)

        else:  # "smart"
            # Bounds only expand: min can decrease, max can increase.
            if self._auto_t_min is None:
                if self._heatmap_auto:
                    self._auto_t_min = t_min_now
                    self._auto_t_max = t_max_now
                else:
                    self._auto_t_min = self._heatmap_t_min
                    self._auto_t_max = self._heatmap_t_max
            self._auto_t_min = min(self._auto_t_min, t_min_now)
            self._auto_t_max = max(self._auto_t_max, t_max_now)
            return self._apply_min_range(self._auto_t_min, self._auto_t_max)

    def _apply_min_range(self, t_min: float, t_max: float) -> tuple[float, float]:
        min_rng = max(0.1, self._min_auto_range_k)
        if t_max - t_min < min_rng:
            mid = (t_min + t_max) / 2.0
            t_min = mid - min_rng / 2.0
            t_max = mid + min_rng / 2.0
        return t_min, t_max

    def _draw_cell_text(self, painter: QPainter, g: Grid, cp: int, zoom: float,
                        r0: int, r1: int, c0: int, c1: int) -> None:
        """Draw per-cell text: label (always shown when set) or abbr (only if show_abbr)."""
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
                if cell.material.is_vacuum:
                    continue
                text = (cell.label if (cell.label and self._show_label) else "") or (cell.material.abbr if self._show_abbr else "")
                if not text:
                    continue
                if self._view_mode == "heatmap":
                    bg = heatmap_color(self._display_temp(cell), t_min, t_max)
                else:
                    bg = cell_color(cell)
                painter.setPen(text_color_for_bg(bg))
                painter.drawText(
                    QRectF(c * cp + pad, r * cp, cp - pad * 2, cp - pad),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    text,
                )

    def _build_mat_image(self) -> QImage:
        """Build a full-grid QImage for material view; rebuilt only when dirty."""
        g = self._grid
        cp = CELL_PX
        img = QImage(g.cols * cp, g.rows * cp, QImage.Format.Format_RGB32)
        img.fill(self._BG_COLOR)
        p = QPainter(img)
        for r in range(g.rows):
            for c in range(g.cols):
                p.fillRect(c * cp, r * cp, cp, cp, cell_color(g.cell(r, c)))
        p.end()
        return img

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

            amb_display = _units.to_display(g.ambient_temp_k)

            for r in range(r0, r1):
                for c in range(c0, c1):
                    cell = g.cell(r, c)
                    if cell.material.is_vacuum:
                        continue
                    t  = self._display_temp(cell)
                    bg = heatmap_color(t, t_min, t_max)
                    painter.setPen(text_color_for_bg(bg))
                    if self._show_delta:
                        delta = _units.to_display(t) - amb_display
                        sign = "+" if delta >= 0 else ""
                        label = f"{sign}{delta:.0f}{_units.suffix()}"
                    else:
                        label = f"{_units.to_display(t):.0f}{_units.suffix()}"
                    painter.drawText(
                        QRectF(c * cp, r * cp, cp, cp),
                        Qt.AlignmentFlag.AlignCenter,
                        label,
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

    def _draw_hotspot(self, painter: QPainter, g: Grid, cp: int,
                      r0: int, r1: int, c0: int, c1: int) -> None:
        """Tint cells above the hotspot threshold with a semi-transparent red overlay."""
        thresh = self._hotspot_threshold_k
        fill   = QColor(220, 40, 40, 90)
        pen    = QPen(QColor(255, 60, 60))
        pen.setCosmetic(True)
        pen.setWidth(1)
        for r in range(r0, r1):
            for c in range(c0, c1):
                cell = g.cell(r, c)
                if not cell.material.is_vacuum and self._display_temp(cell) > thresh:
                    painter.fillRect(c * cp, r * cp, cp, cp, fill)
                    painter.setPen(pen)
                    painter.drawRect(c * cp, r * cp, cp - 1, cp - 1)

    def _draw_flux_view(self, painter: QPainter, g: Grid, cp: int,
                       r0: int, r1: int, c0: int, c1: int) -> None:
        """Draw cells colored by total heat flow rate (W) using the active heatmap palette.

        Heat flow through each cell: Q = sum of |k_eff * dT| across all
        interfaces (W for 2D with unit depth). Stores flow bounds in
        _flow_bounds for the legend.
        """
        rows, cols = g.rows, g.cols
        bg = self._BG_COLOR

        # Compute total heat flow (W) for all visible cells.
        flow_map: dict[tuple[int, int], float] = {}
        min_flow = float("inf")
        max_flow = 0.0

        for r in range(r0, r1):
            for c in range(c0, c1):
                cell = g.cell(r, c)
                if cell.material.is_vacuum:
                    continue
                k_c = cell.material.k
                if k_c == 0:
                    continue
                T_c = cell.temperature
                total_q = 0.0

                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        nb = g.cell(nr, nc)
                        if not nb.material.is_vacuum and nb.material.k > 0:
                            k_eff = 2.0 * k_c * nb.material.k / (k_c + nb.material.k)
                            total_q += abs(k_eff * (nb.temperature - T_c))

                mag = total_q * 0.5
                flow_map[(r, c)] = mag
                if mag > max_flow:
                    max_flow = mag
                if mag < min_flow:
                    min_flow = mag

        if min_flow == float("inf"):
            min_flow = 0.0
        if max_flow <= min_flow:
            max_flow = min_flow + 1.0

        # Store for legend
        self._flow_bounds = (min_flow, max_flow)

        # Draw cell backgrounds using heatmap palette
        for r in range(r0, r1):
            for c in range(c0, c1):
                cell = g.cell(r, c)
                if cell.material.is_vacuum:
                    painter.fillRect(c * cp, r * cp, cp, cp, bg)
                    continue
                mag = flow_map.get((r, c), 0.0)
                color = heatmap_color(mag, min_flow, max_flow)
                painter.fillRect(c * cp, r * cp, cp, cp, color)

        # Draw heat flow values as text in each cell
        font = QFont()
        font.setPixelSize(max(7, int(cp * 0.28)))
        painter.setFont(font)

        for r in range(r0, r1):
            for c in range(c0, c1):
                cell = g.cell(r, c)
                if cell.material.is_vacuum:
                    continue
                mag = flow_map.get((r, c), 0.0)
                color = heatmap_color(mag, min_flow, max_flow)
                painter.setPen(text_color_for_bg(color))
                if mag < 1e-9:
                    label = "0 W"
                elif mag >= 1000:
                    label = f"{mag / 1000:.1f}kW"
                elif mag >= 1:
                    label = f"{mag:.1f}W"
                elif mag >= 0.001:
                    label = f"{mag * 1000:.0f}mW"
                else:
                    label = f"{mag * 1e6:.0f}\u00b5W"
                painter.drawText(
                    QRectF(c * cp, r * cp, cp, cp),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )

    def _draw_heat_vectors(self, painter: QPainter, g: Grid, cp: int,
                           zoom: float,
                           r0: int, r1: int, c0: int, c1: int) -> None:
        """Draw heat flow direction arrows on cells in heatmap/flow modes.

        Computes per-cell (q_x, q_y) from interface fluxes using harmonic-mean k.
        Arrow length proportional to magnitude. Decimated every Nth cell for
        large grids to avoid visual clutter.
        """
        rows, cols = g.rows, g.cols
        cell_px_screen = cp * zoom

        # Auto-decimation: show every Nth cell based on zoom level
        if cell_px_screen >= 24:
            skip = 1
        elif cell_px_screen >= 12:
            skip = 2
        elif cell_px_screen >= 6:
            skip = 4
        else:
            skip = 8

        # Compute (q_x, q_y) for each visible cell
        vectors: list[tuple[int, int, float, float]] = []  # (r, c, qx, qy)
        max_mag = 0.0

        for r in range(r0, r1):
            if r % skip != 0:
                continue
            for c in range(c0, c1):
                if c % skip != 0:
                    continue
                cell = g.cell(r, c)
                if cell.material.is_vacuum or cell.material.k == 0:
                    continue
                k_c = cell.material.k
                T_c = cell.temperature
                # Fourier's law: q = -k * grad(T). Compute cell-centered flux
                # by averaging interface fluxes. Always divide by 2 so boundary
                # cells (with one missing neighbor = zero flux) stay consistent.
                qx = 0.0
                qy = 0.0

                # Right interface: flux in +x direction
                if c + 1 < cols:
                    nb = g.cell(r, c + 1)
                    if not nb.material.is_vacuum and nb.material.k > 0:
                        k_eff = 2.0 * k_c * nb.material.k / (k_c + nb.material.k)
                        qx += k_eff * (T_c - nb.temperature)  # positive = heat flows right (hot→cold)
                # Left interface: flux in +x direction
                if c - 1 >= 0:
                    nb = g.cell(r, c - 1)
                    if not nb.material.is_vacuum and nb.material.k > 0:
                        k_eff = 2.0 * k_c * nb.material.k / (k_c + nb.material.k)
                        qx += k_eff * (nb.temperature - T_c)  # positive = heat flows right (hot→cold)
                # Bottom interface: flux in +y direction (downward in screen)
                if r + 1 < rows:
                    nb = g.cell(r + 1, c)
                    if not nb.material.is_vacuum and nb.material.k > 0:
                        k_eff = 2.0 * k_c * nb.material.k / (k_c + nb.material.k)
                        qy += k_eff * (T_c - nb.temperature)
                # Top interface: flux in +y direction
                if r - 1 >= 0:
                    nb = g.cell(r - 1, c)
                    if not nb.material.is_vacuum and nb.material.k > 0:
                        k_eff = 2.0 * k_c * nb.material.k / (k_c + nb.material.k)
                        qy += k_eff * (nb.temperature - T_c)

                qx *= 0.5
                qy *= 0.5

                mag = math.sqrt(qx * qx + qy * qy)
                if mag > 0:
                    vectors.append((r, c, qx, qy))
                    if mag > max_mag:
                        max_mag = mag

        if not vectors or max_mag == 0:
            return

        # Draw arrows in scene coordinates (scale naturally with zoom).
        # Two-pass rendering: dark outline first, then bright fill for contrast.
        max_len = cp * 0.38  # arrow half-length (tip to center)
        head_len = cp * 0.14  # arrowhead barb length
        shaft_w = max(1.0, cp * 0.06)  # shaft thickness in scene coords

        for pass_idx in range(2):
            if pass_idx == 0:
                # Outline pass: dark, slightly thicker
                pen = QPen(QColor(0, 0, 0, 180))
                pen.setWidthF(shaft_w + max(1.0, cp * 0.03))
            else:
                # Fill pass: bright white
                pen = QPen(QColor(255, 255, 255, 230))
                pen.setWidthF(shaft_w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            for r, c, qx, qy in vectors:
                mag = math.sqrt(qx * qx + qy * qy)
                frac = mag / max_mag
                length = max_len * max(frac, 0.15)  # floor so tiny arrows are still visible

                # Normalize direction
                dx_n = qx / mag
                dy_n = qy / mag

                # Cell center
                cx = c * cp + cp * 0.5
                cy = r * cp + cp * 0.5

                # Shaft: from tail to tip
                tx = cx + dx_n * length
                ty = cy + dy_n * length
                fx = cx - dx_n * length * 0.5
                fy = cy - dy_n * length * 0.5
                painter.drawLine(QPointF(fx, fy), QPointF(tx, ty))

                # Arrowhead barbs (extend backward from tip toward tail)
                angle = math.atan2(dy_n, dx_n)
                hl = head_len * max(frac, 0.3)
                for da in (2.6, -2.6):  # ~149 degrees from shaft direction
                    hx = tx + hl * math.cos(angle + da)
                    hy = ty + hl * math.sin(angle + da)
                    painter.drawLine(QPointF(tx, ty), QPointF(hx, hy))

    def _draw_isotherms(self, painter: QPainter, g: Grid, cp: int,
                        r0: int, r1: int, c0: int, c1: int) -> None:
        """Draw isotherm contour lines using marching squares.

        For each 2x2 quad of cell centers, classify corners as above/below
        the threshold and draw interpolated line segments. This produces
        smooth, connected contours without staircase artifacts.
        """
        t_min, t_max = self._frame_bounds
        if t_max <= t_min:
            return
        interval = self._isotherm_interval_k
        pen = QPen(self._isotherm_color)
        pen.setCosmetic(True)
        pen.setWidth(self._isotherm_line_width)
        painter.setPen(pen)

        half = cp / 2.0

        # Build temperature grid at cell centers (using internal K for comparison)
        rows, cols = g.rows, g.cols
        # Cache cell temps for the visible region (+ 1 margin for quads)
        r_lo = max(r0, 0)
        r_hi = min(r1 + 1, rows)
        c_lo = max(c0, 0)
        c_hi = min(c1 + 1, cols)

        # Get display temps for visible cells
        temps: dict[tuple[int, int], float | None] = {}
        for r in range(r_lo, r_hi):
            for c in range(c_lo, c_hi):
                cell = g.cell(r, c)
                if cell.material.is_vacuum:
                    temps[(r, c)] = None
                else:
                    temps[(r, c)] = self._display_temp(cell)

        def _interp(va: float, vb: float, thresh: float,
                    ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
            dt = vb - va
            frac = (thresh - va) / dt if abs(dt) > 1e-6 else 0.5
            return ax + frac * (bx - ax), ay + frac * (by - ay)

        t_range = t_max - t_min
        if t_range > 0 and interval > 0:
            interval = max(interval, t_range / 500)
        first_thresh = math.ceil(t_min / interval) * interval
        thresh = first_thresh
        _max_passes = 500

        while thresh <= t_max and _max_passes > 0:
            # Marching squares over quads: corners are cell centers (r,c), (r,c+1), (r+1,c+1), (r+1,c)
            for r in range(r_lo, r_hi - 1):
                for c in range(c_lo, c_hi - 1):
                    v_tl = temps.get((r, c))
                    v_tr = temps.get((r, c + 1))
                    v_bl = temps.get((r + 1, c))
                    v_br = temps.get((r + 1, c + 1))
                    if v_tl is None or v_tr is None or v_bl is None or v_br is None:
                        continue

                    # Classify corners: 1 = above threshold
                    case = ((1 if v_tl >= thresh else 0) |
                            (2 if v_tr >= thresh else 0) |
                            (4 if v_br >= thresh else 0) |
                            (8 if v_bl >= thresh else 0))
                    if case == 0 or case == 15:
                        continue

                    # Corner pixel positions (cell centers)
                    tl_x, tl_y = c * cp + half, r * cp + half
                    tr_x, tr_y = (c + 1) * cp + half, r * cp + half
                    br_x, br_y = (c + 1) * cp + half, (r + 1) * cp + half
                    bl_x, bl_y = c * cp + half, (r + 1) * cp + half

                    # Edge interpolation points
                    def top():
                        return _interp(v_tl, v_tr, thresh, tl_x, tl_y, tr_x, tr_y)
                    def right():
                        return _interp(v_tr, v_br, thresh, tr_x, tr_y, br_x, br_y)
                    def bottom():
                        return _interp(v_bl, v_br, thresh, bl_x, bl_y, br_x, br_y)
                    def left():
                        return _interp(v_tl, v_bl, thresh, tl_x, tl_y, bl_x, bl_y)

                    # Marching squares lookup: each case produces 1-2 line segments
                    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
                    if case in (1, 14):
                        segments.append((top(), left()))
                    elif case in (2, 13):
                        segments.append((top(), right()))
                    elif case in (3, 12):
                        segments.append((left(), right()))
                    elif case in (4, 11):
                        segments.append((right(), bottom()))
                    elif case == 5:
                        # Saddle: use center value to disambiguate
                        center = (v_tl + v_tr + v_bl + v_br) / 4.0
                        if center >= thresh:
                            segments.append((top(), right()))
                            segments.append((left(), bottom()))
                        else:
                            segments.append((top(), left()))
                            segments.append((right(), bottom()))
                    elif case in (6, 9):
                        segments.append((top(), bottom()))
                    elif case in (7, 8):
                        segments.append((left(), bottom()))
                    elif case == 10:
                        center = (v_tl + v_tr + v_bl + v_br) / 4.0
                        if center >= thresh:
                            segments.append((top(), left()))
                            segments.append((right(), bottom()))
                        else:
                            segments.append((top(), right()))
                            segments.append((left(), bottom()))

                    for (x0, y0), (x1, y1) in segments:
                        painter.drawLine(int(x0), int(y0), int(x1), int(y1))

            thresh += interval
            _max_passes -= 1

    def _draw_color_legend(self, painter: QPainter) -> None:
        """Draw a vertical color scale bar in the viewport corner.

        In heatmap mode: shows temperature range.
        In flux mode: shows flux magnitude range (W/m2).
        """
        is_flux = self._view_mode == "flow"
        if is_flux:
            v_min, v_max = self._flow_bounds
        else:
            v_min, v_max = self._frame_bounds

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
            v = v_max - frac * (v_max - v_min)
            grad.setColorAt(frac, heatmap_color(v, v_min, v_max))

        painter.fillRect(x, y, BAR_W, bar_h, QBrush(grad))

        border_pen = QPen(QColor(100, 100, 100))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawRect(x, y, BAR_W - 1, bar_h - 1)

        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QColor(200, 200, 200))

        if is_flux:
            def _fmt_flux(v: float) -> str:
                if v >= 1000:
                    return f"{v / 1000:.1f} kW"
                return f"{v:.0f} W"
            painter.drawText(x + BAR_W + 4, y + 11, _fmt_flux(v_max))
            painter.drawText(x + BAR_W + 4, y + bar_h, _fmt_flux(v_min))
        else:
            suf = _units.suffix()
            painter.drawText(x + BAR_W + 4, y + 11,
                             f"{_units.to_display(v_max):.0f} {suf}")
            painter.drawText(x + BAR_W + 4, y + bar_h,
                             f"{_units.to_display(v_min):.0f} {suf}")

        painter.restore()
