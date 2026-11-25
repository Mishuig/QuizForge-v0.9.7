"""Спільні будівельні блоки адаптивної верстки (grid + stretch)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame, QPushButton, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from core import ui_theme
from core.ui_theme import logo_pixmap


class ThemedLogo(QLabel):
    def __init__(self, name: str, size: int, parent=None):
        super().__init__(parent)
        self._name, self._size = name, size
        self._refresh()
        ui_theme.bus.changed.connect(self._refresh)

    def _refresh(self, *_args):
        pm = logo_pixmap(self._name, self._size)
        if not pm.isNull():
            self.setPixmap(pm)


class ThemeToggle(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("themeToggle")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Перемкнути тему")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clicked.connect(lambda: ui_theme.toggle_theme())
        ui_theme.bus.changed.connect(self._sync)
        self._sync()

    def _sync(self, *_args):
        self.setText("☀ Світла" if ui_theme.current_theme() == "dark" else "☾ Темна")


def field(label: str, widget: QWidget) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    cap = QLabel(label)
    cap.setObjectName("fieldLabel")
    lay.addWidget(cap)
    lay.addWidget(widget)
    return box


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


def align_center(label: QLabel) -> QLabel:
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


def icon_button(icon_name: str, tooltip: str, color: str = "#E6EDF7", size: int = 20, danger: bool = False, accent: bool = False) -> QPushButton:
    try:
        import qtawesome as qta
        icon = qta.icon(icon_name, color=color)
        btn = QPushButton(icon, "")
    except Exception:
        btn = QPushButton(tooltip[:2])
    btn.setObjectName("iconBtn")
    btn.setToolTip(tooltip)
    btn.setIconSize(QSize(size, size))
    btn.setFixedSize(size + 16, size + 16)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if danger:
        btn.setProperty("danger", True)
    if accent:
        btn.setProperty("accent", True)
    return btn
