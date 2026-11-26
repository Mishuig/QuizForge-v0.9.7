"""Спільні будівельні блоки адаптивної верстки."""

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


def brand_row(logo: str = "logo-client.svg", size: int = 40, centered: bool = True) -> QWidget:
    """Логотип + назва QuizForge."""
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(12)
    if centered:
        row.addStretch(1)
    icon = ThemedLogo(logo, size)
    name = QLabel("QuizForge")
    name.setObjectName("logoLabel")
    row.addWidget(icon)
    row.addWidget(name)
    row.addStretch(1)
    return w


def centered_card(screen: QWidget, max_width: int = 520, min_width: int = 300):
    """Центрована картка. Повертає (card, card_layout)."""
    grid = QGridLayout(screen)
    grid.setContentsMargins(24, 24, 24, 24)
    grid.setRowStretch(0, 1)
    grid.setRowStretch(2, 1)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1000)
    grid.setColumnStretch(2, 1)
    card = QFrame()
    card.setObjectName("card")
    card.setMinimumWidth(min_width)
    card.setMaximumWidth(max_width)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(36, 32, 36, 32)
    lay.setSpacing(16)
    grid.addWidget(card, 1, 1)
    grid.addWidget(ThemeToggle(), 0, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
    return card, lay


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


class AdaptiveButton(QPushButton):
    def __init__(self, text: str, short: str = None, parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self._short_text = short or text[:6]
        self._min_font = 8
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        available = self.width() - 16
        if available <= 0:
            return
        font = self.font()
        for size in range(font.pointSize() or 12, self._min_font - 1, -1):
            font.setPointSize(size)
            fm = QFontMetrics(font)
            if fm.horizontalAdvance(self._full_text) <= available:
                self.setFont(font)
                self.setText(self._full_text)
                return
        font.setPointSize(self._min_font)
        self.setFont(font)
        self.setText(self._short_text)


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
