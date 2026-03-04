from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget,
)


class MainWindow(QMainWindow):
    new_grid_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyTherm")
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)
        self._build_menu()
        self._build_central()
        self.statusBar().showMessage("Ready")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        new_action = file_menu.addAction("New Grid...")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_grid_requested)

    def _build_central(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar — fixed 280px; later steps replace the placeholder label
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(280)
        self.sidebar.setObjectName("sidebar")
        sidebar_inner = QVBoxLayout(self.sidebar)
        sidebar_inner.setContentsMargins(8, 8, 8, 8)
        _placeholder(sidebar_inner, "Sidebar\n(Step 6: material picker\nStep 7: properties panel)")

        # Thin separator line between sidebar and canvas
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #222;")

        # Canvas area — expands to fill remaining space; Step 5 slots in the grid view
        self.canvas_area = QWidget()
        canvas_inner = QHBoxLayout(self.canvas_area)
        _placeholder(canvas_inner, "Canvas\n(Step 5: grid view)")

        layout.addWidget(self.sidebar)
        layout.addWidget(sep)
        layout.addWidget(self.canvas_area, stretch=1)
        self.setCentralWidget(root)

    # --- Replacement hooks for later steps ---

    def set_canvas_widget(self, widget: QWidget) -> None:
        """Slot the real grid view into the canvas area (called in Step 5)."""
        _replace_layout_contents(self.canvas_area.layout(), widget)

    def set_sidebar_widget(self, widget: QWidget) -> None:
        """Slot the real sidebar into the left panel (called in Step 6)."""
        _replace_layout_contents(self.sidebar.layout(), widget)


# --- Helpers ---

def _placeholder(layout: QHBoxLayout | QVBoxLayout, text: str) -> None:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color: #555; font-size: 11px;")
    layout.addWidget(lbl)


def _replace_layout_contents(layout, widget: QWidget) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    layout.addWidget(widget)
