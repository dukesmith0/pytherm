from __future__ import annotations

from collections import deque
from copy import copy

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsView

from src.models.material import Material
from src.simulation.cell import Cell
from src.ui.grid_scene import CELL_PX, GridScene
from src.ui.tooltip_widget import CellTooltip


def _bresenham_line(r1: int, c1: int, r2: int, c2: int) -> list[tuple[int, int]]:
    """Return all grid cells on the rasterised line from (r1,c1) to (r2,c2)."""
    cells: list[tuple[int, int]] = []
    dr = abs(r2 - r1)
    dc = abs(c2 - c1)
    r, c = r1, c1
    sr = 1 if r2 > r1 else -1
    sc = 1 if c2 > c1 else -1

    if dc > dr:
        err = dc // 2
        while c != c2:
            cells.append((r, c))
            err -= dr
            if err < 0:
                r += sr
                err += dc
            c += sc
    else:
        err = dr // 2
        while r != r2:
            cells.append((r, c))
            err -= dc
            if err < 0:
                c += sc
                err += dr
            r += sr
    cells.append((r2, c2))
    return cells


def _rect_cells(r1: int, c1: int, r2: int, c2: int) -> list[tuple[int, int]]:
    return [
        (r, c)
        for r in range(min(r1, r2), max(r1, r2) + 1)
        for c in range(min(c1, c2), max(c1, c2) + 1)
    ]


class GridView(QGraphicsView):
    # Emitted on any selection commit — list of (row, col) tuples (length >= 1)
    cells_selected = pyqtSignal(list)
    # Emitted whenever at least one cell's material is changed by drawing
    cell_painted = pyqtSignal()
    # Emitted once at the very start of each paint stroke (before any cells change)
    paint_started = pyqtSignal()
    # Emitted when middle-click eyedropper picks a material
    material_eyedropped = pyqtSignal(object)

    def __init__(self, scene: GridScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        # AnchorUnderMouse: scale() keeps the point under the cursor fixed in screen space
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Do NOT call setBackgroundBrush — it prevents scene.drawBackground from being called
        self._fitted = False

        # Drawing / interaction state
        self._mode: str = "draw"              # "draw" | "select" | "fill"
        self._active_material: Material | None = None
        self._painting: bool = False          # True during regular left-drag paint
        self._drawing_locked: bool = False    # True while sim is running

        # Selection state
        self._selection: set[tuple[int, int]] = set()
        self._rect_anchor: tuple[int, int] | None = None   # shift+drag rect
        self._line_anchor: tuple[int, int] | None = None   # ctrl+drag Bresenham
        self._current_line: list[tuple[int, int]] = []

        # Middle-click pan state
        self._mid_drag_pos = None

        # Hover tooltip
        self._tooltip = CellTooltip()
        self._dx_m: float = 0.01   # physical cell size in metres; updated by set_dx()
        self.setMouseTracking(True)

        # Rectangular clipboard for Ctrl+C/V in select mode.
        # Stores list of (dr, dc, Cell) where (dr, dc) is offset from top-left of copied selection.
        self._cell_clipboard: list[tuple[int, int, Cell]] | None = None

        # Paint temperature override (None = use cell's existing temperature)
        self._paint_temp: float | None = None

        # Draw brush heat settings (stamped onto painted cells)
        self._draw_is_fixed: bool = False
        self._draw_fixed_temp_k: float = 293.15
        self._draw_is_flux: bool = False
        self._draw_flux_q: float = 0.0
        self._draw_label: str = ""

        # Vacuum material reference for Delete key (set by app.py via set_vacuum_material)
        self._vacuum_material: Material | None = None

    # --- Public API (called by toolbar / sidebar) ---

    def set_dx(self, dx_m: float) -> None:
        """Update the cell size used for energy calculations in the hover tooltip."""
        self._dx_m = dx_m

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._cancel_anchors()

    def set_active_material(self, material: Material) -> None:
        self._active_material = material

    def set_drawing_locked(self, locked: bool) -> None:
        """Disable painting while the simulation is running."""
        self._drawing_locked = locked
        if locked:
            self._painting = False

    def set_paint_temp(self, temp_k: float | None) -> None:
        """Set temperature override applied on each paint stroke (None = don't override)."""
        self._paint_temp = temp_k

    def set_draw_heat_settings(self, is_fixed: bool, fixed_temp_k: float,
                               is_flux: bool, flux_q: float) -> None:
        """Update the heat boundary settings stamped onto painted cells."""
        self._draw_is_fixed = is_fixed
        self._draw_fixed_temp_k = fixed_temp_k
        self._draw_is_flux = is_flux
        self._draw_flux_q = flux_q

    def set_draw_label(self, label: str) -> None:
        """Set the label stamped onto painted cells (empty string = keep existing)."""
        self._draw_label = label

    def set_vacuum_material(self, material: Material) -> None:
        """Set the vacuum material used by the Delete key to clear selected cells."""
        self._vacuum_material = material

    def zoom_to_selection(self) -> None:
        """Fit the view to the current selection bounding box."""
        if not self._selection:
            return
        rows = [r for r, c in self._selection]
        cols = [c for r, c in self._selection]
        r0, r1 = min(rows), max(rows)
        c0, c1 = min(cols), max(cols)
        self.fitInView(
            QRectF(c0 * CELL_PX - 8, r0 * CELL_PX - 8,
                   (c1 - c0 + 1) * CELL_PX + 16, (r1 - r0 + 1) * CELL_PX + 16),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    # --- Mouse events ---

    def mousePressEvent(self, event) -> None:
        cell  = self._cell_at(event.pos())
        ctrl  = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        if event.button() == Qt.MouseButton.LeftButton:
            if ctrl and cell and self._mode == "select":
                # Ctrl+click in select mode: toggle individual cell
                self._cancel_anchors()
                new_sel = set(self._selection)
                if cell in new_sel:
                    new_sel.discard(cell)
                else:
                    new_sel.add(cell)
                if new_sel:
                    self._do_select(list(new_sel))
                else:
                    self._clear_selection()
                    self.scene().refresh()

            elif ctrl and cell:
                # Ctrl: start Bresenham line anchor (draw/fill mode)
                self._cancel_painting()
                self._rect_anchor = None
                self._line_anchor = cell
                self._current_line = [cell]
                self.scene().set_line_preview(self._current_line)

            elif shift and cell:
                # Shift: start rectangle selection anchor
                self._cancel_painting()
                self._line_anchor = None
                self._current_line = []
                self._rect_anchor = cell
                self.scene().set_preview_rect(*cell, *cell)

            else:
                # No modifier: paint/fill (draw/fill mode) or single-cell select (select mode)
                self._cancel_anchors()
                if self._mode == "draw" and not self._drawing_locked:
                    self._clear_selection()   # plain paint clears any prior selection
                    self._painting = True
                    if cell:
                        self.paint_started.emit()  # snapshot before first stroke cell
                        self._paint_cell(*cell)
                        self.scene().refresh()
                elif self._mode == "fill" and not self._drawing_locked and cell:
                    self._clear_selection()
                    self.paint_started.emit()
                    self._flood_fill(*cell)
                    self.scene().refresh()
                elif cell:
                    if self._selection == {cell}:
                        self._clear_selection()
                        self.cells_selected.emit([])
                        self.scene().refresh()
                    else:
                        self._do_select([cell])
                elif self._mode == "select" and self._selection:
                    self._clear_selection()
                    self.cells_selected.emit([])
                    self.scene().refresh()

        elif event.button() == Qt.MouseButton.MiddleButton:
            if cell and self._mode == "draw":
                # Middle-click eyedropper: pick the cell's material as active
                mat = self.scene()._grid.cell(*cell).material
                self.set_active_material(mat)
                self.material_eyedropped.emit(mat)
            else:
                self._mid_drag_pos = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

        elif event.button() == Qt.MouseButton.RightButton and cell:
            self._cancel_anchors()
            self._do_select([cell])

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        cell = self._cell_at(event.pos())

        # Middle-click pan
        if self._mid_drag_pos is not None and event.buttons() & Qt.MouseButton.MiddleButton:
            delta = event.pos() - self._mid_drag_pos
            self._mid_drag_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())

        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._line_anchor and cell:
                line = _bresenham_line(*self._line_anchor, *cell)
                if line != self._current_line:
                    self._current_line = line
                    self.scene().set_line_preview(line)

            elif self._rect_anchor and cell:
                self.scene().set_preview_rect(*self._rect_anchor, *cell)

            elif self._painting and not self._drawing_locked and cell:
                self._paint_cell(*cell)
                self.scene().refresh()

        # Hover tooltip — hide while actively interacting
        busy = self._painting or self._line_anchor or self._rect_anchor
        if cell and not busy:
            g = self.scene()._grid
            row, col = cell
            self._tooltip.update_cell(g.cell(row, col), self._dx_m, g.ambient_temp_k, row, col)
            self._tooltip.move_near(self.mapToGlobal(event.pos()))
            self._tooltip.show()
        else:
            self._tooltip.hide()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._mid_drag_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if event.button() == Qt.MouseButton.LeftButton:
            if self._line_anchor and self._current_line:
                cells = list(self._current_line)
                if self._mode == "draw" and not self._drawing_locked:
                    self.paint_started.emit()  # snapshot before line commit
                    for r, c in cells:
                        self._paint_cell(r, c)
                    self.scene().refresh()
                self._line_anchor = None
                self._current_line = []
                self.scene().clear_preview()
                self._do_select(cells)

            elif self._rect_anchor is not None:
                cell = self._cell_at(event.pos())
                cells = _rect_cells(*self._rect_anchor, *(cell if cell else self._rect_anchor))
                if self._mode == "draw" and not self._drawing_locked:
                    self.paint_started.emit()  # snapshot before rect commit
                    for r, c in cells:
                        self._paint_cell(r, c)
                    self.scene().refresh()
                self._rect_anchor = None
                self.scene().clear_preview()
                self._do_select(cells)

            self._painting = False

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self._tooltip.hide()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        key  = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if key == Qt.Key.Key_Escape:
            self._cancel_anchors()
            if self._selection:
                self._clear_selection()
                self.cells_selected.emit([])
                self.scene().refresh()
        elif (key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
              and self._mode == "select"
              and self._selection
              and not self._drawing_locked):
            vacuum = self._vacuum_material
            if vacuum is not None:
                self.paint_started.emit()
                for r, c in self._selection:
                    self.scene()._grid.set_cell(r, c, material=vacuum,
                                                is_fixed=False, is_flux=False)
                self.cell_painted.emit()
                self.scene().invalidate_fixed_cells()
                self.scene().refresh()
        elif ctrl and key == Qt.Key.Key_A and self._mode == "select":
            g = self.scene()._grid
            cells = [(r, c) for r in range(g.rows) for c in range(g.cols)
                     if not g.cell(r, c).material.is_vacuum]
            if cells:
                self._do_select(cells)
        elif ctrl and key == Qt.Key.Key_C and self._mode == "select" and self._selection:
            r_min = min(r for r, c in self._selection)
            c_min = min(c for r, c in self._selection)
            g = self.scene()._grid
            self._cell_clipboard = [
                (r - r_min, c - c_min, copy(g.cell(r, c)))
                for r, c in self._selection
            ]
        elif (ctrl and key == Qt.Key.Key_V
              and self._mode == "select"
              and self._selection
              and self._cell_clipboard is not None):
            anchor_r = min(r for r, c in self._selection)
            anchor_c = min(c for r, c in self._selection)
            g = self.scene()._grid
            targets = [(anchor_r + dr, anchor_c + dc, cb) for dr, dc, cb in self._cell_clipboard]
            out_of_bounds = [(r, c) for r, c, _ in targets if not (0 <= r < g.rows and 0 <= c < g.cols)]
            if out_of_bounds:
                from PyQt6.QtWidgets import QMessageBox
                answer = QMessageBox.question(
                    self, "Paste Clipped",
                    f"{len(out_of_bounds)} cell(s) fall outside the grid and will be skipped.\n"
                    "Continue with the partial paste?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            self.paint_started.emit()
            for r, c, cb in targets:
                if 0 <= r < g.rows and 0 <= c < g.cols:
                    g.set_cell(r, c, material=cb.material, temperature=cb.temperature,
                               is_fixed=cb.is_fixed, fixed_temp=cb.fixed_temp,
                               is_flux=cb.is_flux, flux_q=cb.flux_q, label=cb.label)
            self.cell_painted.emit()
            self.scene().invalidate_fixed_cells()
            self.scene().refresh()
        else:
            super().keyPressEvent(event)

    # --- Zoom / resize ---

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._fitted:
            self.fit_grid()
            self._fitted = True

    def wheelEvent(self, event) -> None:
        old_pos = self.mapToScene(event.position().toPoint())
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        t = self.transform()
        t.translate(delta.x(), delta.y())
        self.setTransform(t)

    def fit_grid(self) -> None:
        self.fitInView(self.scene().sceneRect().adjusted(-8, -8, 8, 8),
                       Qt.AspectRatioMode.KeepAspectRatio)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self.fit_grid()

    # --- Helpers ---

    def _cell_at(self, viewport_pos) -> tuple[int, int] | None:
        sp  = self.mapToScene(viewport_pos)
        col = int(sp.x() // CELL_PX)
        row = int(sp.y() // CELL_PX)
        g   = self.scene()._grid
        if 0 <= row < g.rows and 0 <= col < g.cols:
            return row, col
        return None

    def _paint_cell(self, row: int, col: int) -> None:
        if self._active_material is not None:
            if self._active_material.is_vacuum:
                self.scene()._grid.set_cell(
                    row, col,
                    material=self._active_material,
                    is_fixed=False,
                    is_flux=False,
                )
            else:
                kwargs: dict = {
                    "material": self._active_material,
                    "temperature": self._paint_temp,
                }
                if self._draw_is_fixed:
                    kwargs.update({
                        "is_fixed": True,
                        "is_flux": False,
                        "fixed_temp": self._draw_fixed_temp_k,
                    })
                elif self._draw_is_flux:
                    kwargs.update({
                        "is_flux": True,
                        "is_fixed": False,
                        "flux_q": self._draw_flux_q,
                    })
                else:
                    kwargs.update({"is_fixed": False, "is_flux": False})
                if self._draw_label:
                    kwargs["label"] = self._draw_label
                self.scene()._grid.set_cell(row, col, **kwargs)
            self.cell_painted.emit()

    def _do_select(self, cells: list[tuple[int, int]]) -> None:
        self._selection = set(cells)
        self.scene().set_multi_selection(self._selection)
        if len(cells) == 1:
            self.scene().set_selected_cell(*cells[0])
        else:
            self.scene().clear_selected_cell()
        self.scene().refresh()
        self.cells_selected.emit(cells)

    def _clear_selection(self) -> None:
        if self._selection:
            self._selection = set()
            self.scene().set_multi_selection(set())
            self.scene().clear_selected_cell()

    def _cancel_anchors(self) -> None:
        self._rect_anchor = None
        self._line_anchor = None
        self._current_line = []
        self.scene().clear_preview()

    def _cancel_painting(self) -> None:
        self._painting = False

    def _flood_fill(self, start_row: int, start_col: int) -> None:
        """BFS flood fill from (start_row, start_col) with the active material."""
        if self._active_material is None:
            return
        grid = self.scene()._grid
        target_id = grid.cell(start_row, start_col).material.id
        if self._active_material.id == target_id:
            return  # painting same material — no-op
        rows, cols = grid.rows, grid.cols
        visited: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque([(start_row, start_col)])
        while queue:
            r, c = queue.popleft()
            if (r, c) in visited or not (0 <= r < rows and 0 <= c < cols):
                continue
            if grid.cell(r, c).material.id != target_id:
                continue
            visited.add((r, c))
            self._paint_cell(r, c)
            queue.extend([(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)])
