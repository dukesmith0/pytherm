from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QDockWidget, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from src.version import VERSION


class MainWindow(QMainWindow):
    new_grid_requested = pyqtSignal()
    open_requested = pyqtSignal()
    open_plot_requested = pyqtSignal()
    welcome_requested = pyqtSignal()
    legend_toggled = pyqtSignal(bool)
    delta_toggled = pyqtSignal(bool)
    diagnostics_requested = pyqtSignal()
    preferences_requested = pyqtSignal()
    save_requested = pyqtSignal()
    save_as_requested = pyqtSignal()
    export_requested = pyqtSignal()
    export_csv_requested = pyqtSignal()
    materials_manager_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    new_plot_requested = pyqtSignal()
    convergence_graph_requested = pyqtSignal()
    command_palette_requested = pyqtSignal()
    find_hottest_requested = pyqtSignal()
    find_coldest_requested = pyqtSignal()
    reset_selection_requested = pyqtSignal()
    resize_grid_requested = pyqtSignal()
    thermal_resistance_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._dirty: bool = False
        self._current_file: str | None = None
        self._save_fn: Callable[[], bool] | None = None  # set in Step 4
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)
        self._build_menu()
        self._build_central()
        self._update_title()
        self.statusBar().showMessage("Ready")

    def _build_menu(self) -> None:
        # ── File ──
        file_menu = self.menuBar().addMenu("File")

        new_action = file_menu.addAction("New Grid...")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_grid_requested)

        file_menu.addSeparator()

        open_action = file_menu.addAction("Open...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_requested)

        self.open_recent_menu = file_menu.addMenu("Open Recent")

        self.open_template_menu = file_menu.addMenu("Open Template")

        file_menu.addSeparator()

        save_action = file_menu.addAction("Save")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_requested)

        save_as_action = file_menu.addAction("Save As...")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_as_requested)

        file_menu.addSeparator()

        open_plot_action = file_menu.addAction("Open Plot...")
        open_plot_action.setToolTip("Open a saved .pythermplot file")
        open_plot_action.triggered.connect(self.open_plot_requested)

        file_menu.addSeparator()

        export_action = file_menu.addAction("Export View as Image...")
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_requested)

        csv_action = file_menu.addAction("Export Cell Data as CSV...")
        csv_action.triggered.connect(self.export_csv_requested)

        file_menu.addSeparator()

        welcome_action = file_menu.addAction("Return to Welcome Screen")
        welcome_action.triggered.connect(self.welcome_requested)

        # ── Edit ──
        edit_menu = self.menuBar().addMenu("Edit")

        self._undo_action = edit_menu.addAction("Undo")
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.triggered.connect(self.undo_requested)

        self._redo_action = edit_menu.addAction("Redo")
        self._redo_action.setShortcut("Ctrl+Shift+Z")
        self._redo_action.triggered.connect(self.redo_requested)

        edit_menu.addSeparator()

        mgr_action = edit_menu.addAction("Materials Manager...")
        mgr_action.triggered.connect(self.materials_manager_requested)

        resize_action = edit_menu.addAction("Resize Grid...")
        resize_action.triggered.connect(self.resize_grid_requested)

        edit_menu.addSeparator()

        reset_sel_action = edit_menu.addAction("Reset Selection to Ambient")
        reset_sel_action.triggered.connect(self.reset_selection_requested)

        # ── View ──
        self._view_menu = self.menuBar().addMenu("View")
        view_menu = self._view_menu

        self._delta_action = view_menu.addAction("Temperature Rise (dT)")
        self._delta_action.setCheckable(True)
        self._delta_action.setShortcut("Ctrl+D")
        self._delta_action.setToolTip("Show each cell's temperature rise (T - T_amb) in heatmap mode")
        self._delta_action.toggled.connect(self.delta_toggled)

        self._legend_action = view_menu.addAction("Temperature Legend")
        self._legend_action.setCheckable(True)
        self._legend_action.setShortcut("Ctrl+L")
        self._legend_action.setToolTip("Show/hide the floating temperature scale overlay")
        self._legend_action.toggled.connect(self.legend_toggled)

        view_menu.addSeparator()

        new_plot_action = view_menu.addAction("New Temperature Plot")
        new_plot_action.setToolTip("Open an additional temperature plot panel")
        new_plot_action.triggered.connect(self.new_plot_requested)

        conv_action = view_menu.addAction("Convergence Graph")
        conv_action.setToolTip("Show convergence rate (dT/dt) vs simulated time")
        conv_action.triggered.connect(self.convergence_graph_requested)

        view_menu.addSeparator()

        hottest_action = view_menu.addAction("Find Hottest Cell")
        hottest_action.setShortcut("Ctrl+Shift+H")
        hottest_action.triggered.connect(self.find_hottest_requested)

        coldest_action = view_menu.addAction("Find Coldest Cell")
        coldest_action.setShortcut("Ctrl+Shift+L")
        coldest_action.triggered.connect(self.find_coldest_requested)

        # ── Analysis ──
        analysis_menu = self.menuBar().addMenu("Analysis")

        rth_action = analysis_menu.addAction("Thermal Resistance Report...")
        rth_action.setToolTip("Compute R_th between source and sink cells")
        rth_action.triggered.connect(self.thermal_resistance_requested)

        # ── Tools ──
        tools_menu = self.menuBar().addMenu("Tools")

        palette_action = tools_menu.addAction("Command Palette...")
        palette_action.setShortcut("Ctrl+Shift+P")
        palette_action.setToolTip("Open the command palette (Ctrl+Shift+P)")
        palette_action.triggered.connect(self.command_palette_requested)

        tools_menu.addSeparator()

        prefs_action = tools_menu.addAction("Preferences...")
        prefs_action.setShortcut("Ctrl+,")
        prefs_action.triggered.connect(self.preferences_requested)

        tools_menu.addSeparator()

        diag_action = tools_menu.addAction("Debug Diagnostics...")
        diag_action.setShortcut("Ctrl+Shift+D")
        diag_action.setToolTip("Show simulation and grid diagnostics")
        diag_action.triggered.connect(self.diagnostics_requested)

        # ── Help ──
        help_menu = self.menuBar().addMenu("Help")

        whats_new = help_menu.addAction("What's New...")
        whats_new.triggered.connect(self._show_changelog)

        help_menu.addSeparator()

        bug_action = help_menu.addAction("Report a Bug...")
        bug_action.triggered.connect(self._open_bug_report)

        about_action = help_menu.addAction("About PyTherm...")
        about_action.triggered.connect(self._show_about)

    def _show_changelog(self) -> None:
        changelog_path = Path(__file__).parent.parent.parent / "CHANGELOG.md"
        try:
            text = changelog_path.read_text(encoding="utf-8")
        except OSError:
            QMessageBox.warning(self, "Changelog", "CHANGELOG.md not found.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("What's New")
        dlg.resize(680, 520)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)

        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setMarkdown(text)
        layout.addWidget(viewer)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        dlg.exec()

    def _show_about(self) -> None:
        from src.ui.welcome_dialog import make_logo_pixmap

        dlg = QDialog(self)
        dlg.setWindowTitle("About PyTherm")
        dlg.setFixedWidth(380)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Dark header matching the welcome dialog aesthetic
        header = QWidget()
        header.setAutoFillBackground(True)
        pal = header.palette()
        pal.setColor(header.backgroundRole(), QColor(22, 22, 42))
        header.setPalette(pal)

        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(20, 18, 20, 18)
        hlayout.setSpacing(16)

        logo = QLabel()
        logo.setPixmap(make_logo_pixmap(60))
        logo.setFixedSize(60, 60)
        hlayout.addWidget(logo)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setContentsMargins(0, 0, 0, 0)

        title = QLabel("PyTherm")
        title.setStyleSheet("color: #fff; font-size: 22px; font-weight: bold;")
        text_col.addWidget(title)

        sub = QLabel("2D Heat Conduction Simulator")
        sub.setStyleSheet("color: #9999cc; font-size: 11px;")
        text_col.addWidget(sub)

        meta = QLabel(f'v{VERSION}  ·  Craig "Duke" Smith  ·  2026')
        meta.setStyleSheet("color: #555577; font-size: 10px;")
        text_col.addWidget(meta)

        gh = QLabel('<a href="https://github.com/dukesmith0/pytherm" '
                    'style="color:#4488bb;">github.com/dukesmith0/pytherm</a>')
        gh.setOpenExternalLinks(True)
        gh.setStyleSheet("font-size: 10px;")
        text_col.addWidget(gh)

        hlayout.addLayout(text_col)
        hlayout.addStretch()
        root.addWidget(header)

        footer = QWidget()
        flayout = QHBoxLayout(footer)
        flayout.setContentsMargins(16, 12, 16, 12)
        flayout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(dlg.accept)
        flayout.addWidget(close_btn)
        root.addWidget(footer)

        dlg.exec()

    def _open_bug_report(self) -> None:
        QDesktopServices.openUrl(QUrl("https://github.com/dukesmith0/pytherm/issues/new"))

    def set_legend_checked(self, checked: bool) -> None:
        self._legend_action.setChecked(checked)

    def add_dock_widget(self, area: Qt.DockWidgetArea, dock: QDockWidget) -> None:
        self.addDockWidget(area, dock)
        self._view_menu.addAction(dock.toggleViewAction())

    def _build_central(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(280)
        self.sidebar.setObjectName("sidebar")
        sidebar_inner = QVBoxLayout(self.sidebar)
        sidebar_inner.setContentsMargins(8, 8, 8, 8)
        _placeholder(sidebar_inner, "Sidebar\n(Step 6: material picker\nStep 7: properties panel)")

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #222;")

        self.canvas_area = QWidget()
        canvas_inner = QHBoxLayout(self.canvas_area)
        _placeholder(canvas_inner, "Canvas\n(Step 5: grid view)")

        layout.addWidget(self.sidebar)
        layout.addWidget(sep)
        layout.addWidget(self.canvas_area, stretch=1)
        self.setCentralWidget(root)

    # --- Dirty tracking ---

    def mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._update_title()

    def mark_clean(self, filepath: str | None = None) -> None:
        self._dirty = False
        self._current_file = filepath
        self._update_title()

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def set_save_fn(self, fn: Callable[[], bool]) -> None:
        """Register the save callback (wired in Step 4)."""
        self._save_fn = fn

    def _update_title(self) -> None:
        name = Path(self._current_file).name if self._current_file else None
        file_part = f" \u2014 {name}" if name else ""
        dirty_part = " *" if self._dirty else ""
        self.setWindowTitle(f"PyTherm{file_part}{dirty_part}")

    # --- Close event ---

    def closeEvent(self, event) -> None:
        if not self._dirty:
            event.accept()
            return

        box = QMessageBox(self)
        box.setWindowTitle("Unsaved Changes")
        box.setText("You have unsaved changes. What would you like to do?")
        box.setIcon(QMessageBox.Icon.Warning)

        save_btn    = box.addButton("Save",             QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("Discard and Exit", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn  = box.addButton("Cancel",           QMessageBox.ButtonRole.RejectRole)  # noqa: F841

        if self._save_fn is None:
            save_btn.setEnabled(False)
            save_btn.setToolTip("Save is not yet available")

        box.exec()
        clicked = box.clickedButton()

        if clicked == save_btn and self._save_fn is not None:
            saved = self._save_fn()
            if saved:
                event.accept()
            else:
                event.ignore()
        elif clicked == discard_btn:
            event.accept()
        else:
            event.ignore()

    # --- Replacement hooks ---

    def set_canvas_widget(self, widget: QWidget) -> None:
        _replace_layout_contents(self.canvas_area.layout(), widget)

    def set_sidebar_widget(self, widget: QWidget) -> None:
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
