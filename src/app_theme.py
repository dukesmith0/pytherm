from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


def _apply_dark_theme(app: QApplication) -> None:
    """Dark CAD-style palette - mimics ANSYS/Fluent look."""
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(45,  45,  45))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Base,            QColor(30,  30,  30))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(55,  55,  55))
    p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Button,          QColor(50,  50,  50))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(0,   150, 136))  # teal accent
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Mid,             QColor(60,  60,  60))
    p.setColor(QPalette.ColorRole.Dark,            QColor(20,  20,  20))
    p.setColor(QPalette.ColorRole.Shadow,          QColor(10,  10,  10))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(35,  35,  35))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(200, 200, 200))
    # Disabled state -- dim text so greyed-out widgets are visually obvious
    dis = QPalette.ColorGroup.Disabled
    p.setColor(dis, QPalette.ColorRole.Text,       QColor(90,  90,  90))
    p.setColor(dis, QPalette.ColorRole.WindowText, QColor(90,  90,  90))
    p.setColor(dis, QPalette.ColorRole.ButtonText, QColor(90,  90,  90))
    p.setColor(dis, QPalette.ColorRole.Base,       QColor(38,  38,  38))
    app.setPalette(p)


def _apply_light_theme(app: QApplication) -> None:
    """Light theme for well-lit environments."""
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(240, 240, 240))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(30,  30,  30))
    p.setColor(QPalette.ColorRole.Base,            QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(245, 245, 245))
    p.setColor(QPalette.ColorRole.Text,            QColor(30,  30,  30))
    p.setColor(QPalette.ColorRole.Button,          QColor(230, 230, 230))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(30,  30,  30))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(0,   120, 110))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Mid,             QColor(200, 200, 200))
    p.setColor(QPalette.ColorRole.Dark,            QColor(160, 160, 160))
    p.setColor(QPalette.ColorRole.Shadow,          QColor(120, 120, 120))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(255, 255, 220))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(30,  30,  30))
    dis = QPalette.ColorGroup.Disabled
    p.setColor(dis, QPalette.ColorRole.Text,       QColor(160, 160, 160))
    p.setColor(dis, QPalette.ColorRole.WindowText, QColor(160, 160, 160))
    p.setColor(dis, QPalette.ColorRole.ButtonText, QColor(160, 160, 160))
    p.setColor(dis, QPalette.ColorRole.Base,       QColor(235, 235, 235))
    app.setPalette(p)


def apply_theme(app: QApplication, theme: str) -> None:
    if theme == "light":
        _apply_light_theme(app)
    else:
        _apply_dark_theme(app)
