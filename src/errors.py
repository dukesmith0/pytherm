from __future__ import annotations

import html
import json
import sys
import traceback
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

if TYPE_CHECKING:
    from types import TracebackType

_GITHUB_ISSUES = "https://github.com/dukesmith0/pytherm/issues"


def _crash_code(exc: BaseException) -> tuple[str, str]:
    """Return (code, hint) based on exception type and origin."""
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
        return "ERR_FILE_CORRUPT", "A data file is corrupt or in an unexpected format."
    if isinstance(exc, (FileNotFoundError, PermissionError, OSError)):
        return "ERR_FILE_IO", "A file could not be read or written."
    if "solver" in tb_str.lower() or "sim_clock" in tb_str.lower():
        return "ERR_SOLVER", "The simulation solver encountered an unexpected error."
    if isinstance(exc, (KeyError, AttributeError, TypeError, ValueError)):
        return "ERR_DATA", "Unexpected data structure -- the file may be from a different version."
    return "ERR_UNKNOWN", f"An unexpected error occurred ({type(exc).__name__})."


class CrashDialog(QDialog):
    def __init__(self, exc: BaseException) -> None:
        super().__init__()
        self.setWindowTitle("PyTherm -- Unexpected Error")
        self.setMinimumWidth(520)

        code, hint = _crash_code(exc)
        tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel(f"<b>Crash code:</b> {code}"))

        msg_lbl = QLabel(hint)
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        exc_lbl = QLabel(f"<b>{html.escape(type(exc).__name__)}:</b> {html.escape(str(exc))}")
        exc_lbl.setWordWrap(True)
        layout.addWidget(exc_lbl)

        self._trace = QPlainTextEdit(tb_text)
        self._trace.setReadOnly(True)
        self._trace.setVisible(False)
        self._trace.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._trace.setMinimumHeight(180)
        layout.addWidget(self._trace)

        self._toggle_btn = QPushButton("Show stack trace")
        self._toggle_btn.clicked.connect(self._toggle_trace)
        layout.addWidget(self._toggle_btn)

        buttons = QDialogButtonBox()
        copy_btn   = buttons.addButton("Copy to Clipboard", QDialogButtonBox.ButtonRole.ActionRole)
        report_btn = buttons.addButton("Report Bug",        QDialogButtonBox.ButtonRole.ActionRole)
        close_btn  = buttons.addButton("Close",             QDialogButtonBox.ButtonRole.RejectRole)

        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(
            f"Crash code: {code}\n\n{tb_text}"
        ))
        report_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_GITHUB_ISSUES)))
        close_btn.clicked.connect(self.reject)

        layout.addWidget(buttons)

    def _toggle_trace(self) -> None:
        visible = not self._trace.isVisible()
        self._trace.setVisible(visible)
        self._toggle_btn.setText("Hide stack trace" if visible else "Show stack trace")
        self.adjustSize()


def install_error_handler() -> None:
    """Replace sys.excepthook with a handler that shows CrashDialog."""

    def _hook(exc_type: type[BaseException], exc_value: BaseException,
               exc_tb: TracebackType | None) -> None:
        # Always print to stderr so the terminal still shows the error
        traceback.print_exception(exc_type, exc_value, exc_tb)
        dlg = CrashDialog(exc_value)
        dlg.exec()

    sys.excepthook = _hook
