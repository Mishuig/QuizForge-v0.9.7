"""Спільні будівельні блоки адаптивної верстки (grid + stretch)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QPushButton,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core import ui_theme
from core.ui_theme import logo_pixmap


class ThemedLogo(QLabel):
    """Логотип, що сам перемальовується при зміні теми (світлий/темний варіант)."""

    def __init__(self, name: str, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name, self._size = name, size
        self._refresh()
        ui_theme.bus.changed.connect(self._refresh)

    def _refresh(self, *_args) -> None:
        pm = logo_pixmap(self._name, self._size)
        if not pm.isNull():
            self.setPixmap(pm)


class ThemeToggle(QPushButton):
    """Перемикач темної/світлої теми. Показує, на яку тему перейде натискання."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("themeToggle")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Перемкнути тему оформлення")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clicked.connect(lambda _checked=False: ui_theme.toggle_theme())
        ui_theme.bus.changed.connect(self._sync)
        self._sync()

    def _sync(self, *_args) -> None:
        self.setText("☀  Світла" if ui_theme.current_theme() == "dark" else "☾  Темна")


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
    """
    Центрована картка, що стискається разом із вікном.
    Сітка 3×3: бічні/верхні комірки розтягуються, центральна колонка має пріоритет до max_width.
    Повертає (card, card_layout).
    """
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
    """Підпис над полем (адаптивніше за QFormLayout)."""
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
    """Кнопка, що скорочує текст при нестачі місця.
    
    Порядок: шрифт до 8pt → прибрати слова → скоротити з «...»
    """
    
    def __init__(self, text: str, short: str | None = None, parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self._short_text = short or self._make_short(text)
        self._min_font = 8
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    
    @staticmethod
    def _make_short(text: str) -> str:
        words = text.split()
        if len(words) <= 1:
            return text[:4] + "…" if len(text) > 4 else text
        return words[0][:6] + "…"
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt()
    
    def _adapt(self):
        available = self.width() - 16  # padding
        if available <= 0:
            return
        fm = self.fontMetrics()
        font = self.font()
        
        # Try full text with decreasing font
        for size in range(font.pointSize(), self._min_font - 1, -1):
            font.setPointSize(size)
            fm = QFontMetrics(font)
            if fm.horizontalAdvance(self._full_text) <= available:
                self.setFont(font)
                self.setText(self._full_text)
                return
        
        # Try short text
        font.setPointSize(self._min_font)
        fm = QFontMetrics(font)
        if fm.horizontalAdvance(self._short_text) <= available:
            self.setFont(font)
            self.setText(self._short_text)
            return
        
        # Fallback
        self.setFont(font)
        self.setText("…")
