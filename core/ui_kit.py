"""Спільні будівельні блоки адаптивної верстки."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame, QPushButton, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from core import ui_theme
from core.ui_theme import logo_pixmap


def icon_button(icon_name: str, tooltip: str, color: str = "#E6EDF7", size: int = 20, danger: bool = False, accent: bool = False) -> QPushButton:
    """Кнопка з іконкою і tooltip."""
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
