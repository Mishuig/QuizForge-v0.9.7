"""Спільні будівельні блоки адаптивної верстки."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QTimer, QPoint, QRect
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame, QPushButton, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
    QVBoxLayout, QWidget, QToolTip, QLayout,
)

from core import ui_theme
from core.ui_theme import logo_pixmap


class FlowLayout(QLayout):
    """Layout що переносить елементи на наступний рядок при нестачі місця."""

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        m = self.contentsMargins()
        effective_rect = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective_rect.x()
        y = effective_rect.y()

        for item in self._items:
            wid = item.widget()
            if not wid or not wid.isVisible():
                continue
            space_x = self._spacing
            space_y = self._spacing
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + m.bottom()


def button_row(*buttons, spacing=8) -> QWidget:
    """Гнучкий рядок кнопок що переноситься на наступний рядок."""
    container = QWidget()
    flow = FlowLayout(container, margin=0, spacing=spacing)
    for btn in buttons:
        flow.addWidget(btn)
    container.setLayout(flow)
    container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    return container


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
        self.setText("☀" if ui_theme.current_theme() == "dark" else "☾")


def brand_row(logo: str = "logo-client.svg", size: int = 40, centered: bool = True) -> QWidget:
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


class DelayedTooltipButton(QPushButton):
    """Кнопка з підказкою з затримкою."""

    def __init__(self, tooltip: str, delay_ms: int = 400, parent=None):
        super().__init__(parent)
        self._tooltip = tooltip
        self._delay_ms = delay_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._show_tooltip)
        self._tooltip_visible = False

    def enterEvent(self, event):
        super().enterEvent(event)
        self._timer.start(self._delay_ms)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._timer.stop()
        if self._tooltip_visible:
            QToolTip.hideText()
            self._tooltip_visible = False

    def _show_tooltip(self):
        if self.underMouse():
            pos = self.mapToGlobal(QPoint(0, self.height() + 4))
            QToolTip.showText(pos, self._tooltip, self)
            self._tooltip_visible = True


def icon_button(
    icon_name: str,
    tooltip: str,
    color: str = "#E6EDF7",
    size: int = 20,
    danger: bool = False,
    accent: bool = False,
    delay_ms: int = 400,
) -> QPushButton:
    """Іконка-кнопка з підказкою з затримкою."""
    try:
        import qtawesome as qta
        icon = qta.icon(icon_name, color=color)
        btn = DelayedTooltipButton(tooltip, delay_ms)
        btn.setIcon(icon)
    except Exception:
        btn = DelayedTooltipButton(tooltip, delay_ms)
        btn.setText(tooltip[:2])
    btn.setObjectName("iconBtn")
    btn.setIconSize(QSize(size, size))
    btn.setFixedSize(size + 16, size + 16)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    if danger:
        btn.setProperty("danger", True)
    if accent:
        btn.setProperty("accent", True)
    return btn
