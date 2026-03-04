from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsView

from src.models.material import Material
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
        self._draw_mode: bool = True
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
        self.setMouseTracking(True)

    # --- Public API (called by toolbar / sidebar) ---

    def set_draw_mode(self, is_draw: bool) -> None:
        self._draw_mode = is_draw
        self._cancel_anchors()

    def set_active_material(self, material: Material) -> None:
        self._active_material = material

    def set_drawing_locked(self, locked: bool) -> None:
        """Disable painting while the simulation is running."""
        self._drawing_locked = locked
        if locked:
            self._painting = False

    # --- Mouse events ---

    def mousePressEvent(self, event) -> None:
        cell  = self._cell_at(event.pos())
        ctrl  = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        if event.button() == Qt.MouseButton.LeftButton:
            if ctrl and cell:
                # Ctrl: start Bresenham line anchor
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
                # No modifier: paint (draw mode) or single-cell select (select mode)
                self._cancel_anchors()
                if self._draw_mode and not self._drawing_locked:
                    self._clear_selection()   # plain paint clears any prior selection
                    self._painting = True
                    if cell:
                        self._paint_cell(*cell)
                        self.scene().refresh()
                elif cell:
                    self._do_select([cell])

        elif event.button() == Qt.MouseButton.MiddleButton:
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
            self._tooltip.update_cell(self.scene()._grid.cell(*cell))
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
                if self._draw_mode and not self._drawing_locked:
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
                if self._draw_mode and not self._drawing_locked:
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
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_anchors()
        super().keyPressEvent(event)

    # --- Zoom / resize ---

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._fitted:
            self.fit_grid()
            self._fitted = True

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

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
            self.scene()._grid.set_cell(row, col, material=self._active_material)

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
