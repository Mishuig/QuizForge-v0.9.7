"""
Власні діалоги QuizForge: однакові відступи, іконки, кнопки та адаптивна верстка.

- ThemedDialog — база для всіх діалогів (заголовок, тіло, кнопки внизу, опційний скрол).
- Msg — заміна QMessageBox зі статичними методами information/warning/critical/question/choice.
- Input — заміна QInputDialog.getText.
Системні файлові діалоги (відкрити/зберегти) залишаються нативними.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

SB = QMessageBox.StandardButton

# (kind -> (символ, колір з QSS))
_KINDS = {
    "information": ("i", "info"),
    "question": ("?", "question"),
    "warning": ("!", "warn"),
    "critical": ("✕", "error"),
    "success": ("✓", "ok"),
}


def _inherit_on_top(dlg: QDialog, parent: QWidget | None) -> None:
    """Якщо головне вікно «поверх усіх» (режим тесту) — діалог теж має бути поверх."""
    if parent is None:
        return
    try:
        if parent.window().windowFlags() & Qt.WindowType.WindowStaysOnTopHint:
            dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    except Exception:
        pass


class ThemedDialog(QDialog):
    """Базовий діалог: [іконка] заголовок / підзаголовок → тіло → роздільник → кнопки."""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "",
        subtitle: str = "",
        kind: str | None = None,
        min_width: int = 440,
        max_width: int | None = None,
        icon_pixmap: QPixmap | None = None,
        centered: bool = False,
        scroll: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("themed")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(min_width)
        if max_width:
            self.setMaximumWidth(max_width)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        _inherit_on_top(self, parent)
        self.clicked_key: object | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # --- шапка
        icon_widget: QLabel | None = None
        if icon_pixmap is not None and not icon_pixmap.isNull():
            icon_widget = QLabel()
            icon_widget.setPixmap(icon_pixmap)
        elif kind in _KINDS:
            glyph, tone = _KINDS[kind]
            icon_widget = QLabel(glyph)
            icon_widget.setObjectName("dialogIcon")
            icon_widget.setProperty("kind", tone)
            icon_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("dialogTitle")
        title_lbl.setWordWrap(True)
        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("subtitleLabel")
        sub_lbl.setWordWrap(True)
        sub_lbl.setVisible(bool(subtitle))

        if centered:
            head = QVBoxLayout()
            head.setSpacing(8)
            if icon_widget:
                head.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.addWidget(title_lbl)
            head.addWidget(sub_lbl)
        else:
            head = QHBoxLayout()
            head.setSpacing(16)
            if icon_widget:
                head.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignTop)
            texts = QVBoxLayout()
            texts.setSpacing(4)
            texts.addWidget(title_lbl)
            texts.addWidget(sub_lbl)
            head.addLayout(texts, 1)
        root.addLayout(head)

        # --- тіло (опційно в скролі, щоб діалог працював на малих вікнах)
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        self.body.setContentsMargins(0, 0, 0, 0)
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            holder = QWidget()
            holder.setLayout(self.body)
            self.body.setContentsMargins(0, 0, 8, 0)
            area.setWidget(holder)
            root.addWidget(area, 1)
        else:
            root.addLayout(self.body, 1)

        # --- кнопки
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)
        self._footer = QHBoxLayout()
        self._footer.setSpacing(10)
        self._footer.addStretch(1)
        root.addLayout(self._footer)

    # ---------------------------------------------------------------- API
    def add_button(
        self,
        text: str,
        *,
        accept: bool = False,
        primary: bool = False,
        danger: bool = False,
        key: object | None = None,
        callback: Callable[[], None] | None = None,
        default: bool = False,
        min_width: int = 110,
    ) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumWidth(min_width)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if primary:
            btn.setObjectName("primaryButton")
        elif danger:
            btn.setObjectName("dangerButton")
        btn.setAutoDefault(default)
        btn.setDefault(default)

        def _clicked() -> None:
            self.clicked_key = key
            if callback:
                callback()
                return
            self.accept() if accept else self.reject()

        btn.clicked.connect(_clicked)
        self._footer.addWidget(btn)
        return btn

    def add_text(self, text: str, selectable: bool = True) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("dialogText")
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.PlainText)
        if selectable:
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.addWidget(lbl)
        return lbl

    def make_error_label(self) -> QLabel:
        """Рядок помилки валідації (замість окремого вікна-попередження)."""
        lbl = QLabel()
        lbl.setObjectName("errorLabel")
        lbl.setWordWrap(True)
        lbl.hide()
        return lbl


class Msg:
    """Drop-in заміна QMessageBox (статичні методи)."""

    StandardButton = QMessageBox.StandardButton
    Icon = QMessageBox.Icon

    _ORDER = (
        (SB.No, "Ні", False),
        (SB.Cancel, "Скасувати", False),
        (SB.Close, "Закрити", False),
        (SB.Yes, "Так", True),
        (SB.Ok, "Гаразд", True),
    )

    @staticmethod
    def _exec(parent, kind, title, text, buttons, default, labels) -> "QMessageBox.StandardButton":
        dlg = ThemedDialog(parent, title, kind=kind, min_width=420, max_width=600)
        dlg.add_text(text)
        chosen: list = []
        fallback = None
        first_accept = True
        for std, label, is_accept in Msg._ORDER:
            if not (buttons & std):
                continue
            label = labels.get(std, label)
            is_default = (default == std) or (default == SB.NoButton and is_accept and first_accept)
            if is_accept and first_accept:
                first_accept = False
            dlg.add_button(
                label,
                accept=is_accept,
                primary=is_accept,
                key=std,
                default=is_default,
                callback=(lambda s=std, a=is_accept: (chosen.append(s), dlg.accept() if a else dlg.reject())),
            )
            if not is_accept and fallback is None:
                fallback = std
        if fallback is None:
            fallback = SB.Ok if (buttons & SB.Ok) else SB.Close
        dlg.exec()
        return chosen[0] if chosen else fallback

    @staticmethod
    def _labels(yes_text, no_text, ok_text, cancel_text) -> dict:
        out = {}
        if yes_text: out[SB.Yes] = yes_text
        if no_text: out[SB.No] = no_text
        if ok_text: out[SB.Ok] = ok_text
        if cancel_text: out[SB.Cancel] = cancel_text
        return out

    @staticmethod
    def information(parent, title, text, buttons=SB.Ok, default=SB.NoButton, *, ok_text=None):
        return Msg._exec(parent, "information", title, text, buttons, default, Msg._labels(None, None, ok_text, None))

    @staticmethod
    def success(parent, title, text, buttons=SB.Ok, default=SB.NoButton, *, ok_text=None):
        return Msg._exec(parent, "success", title, text, buttons, default, Msg._labels(None, None, ok_text, None))

    @staticmethod
    def warning(parent, title, text, buttons=SB.Ok, default=SB.NoButton, *, ok_text=None):
        return Msg._exec(parent, "warning", title, text, buttons, default, Msg._labels(None, None, ok_text, None))

    @staticmethod
    def critical(parent, title, text, buttons=SB.Ok, default=SB.NoButton, *, ok_text=None):
        return Msg._exec(parent, "critical", title, text, buttons, default, Msg._labels(None, None, ok_text, None))

    @staticmethod
    def question(parent, title, text, buttons=SB.Yes | SB.No, default=SB.NoButton, *, yes_text=None, no_text=None):
        return Msg._exec(parent, "question", title, text, buttons, default, Msg._labels(yes_text, no_text, None, None))

    @staticmethod
    def choice(parent, title: str, text: str, choices: list[str], cancel_text: str = "Скасувати") -> int:
        """Кілька дій + «Скасувати». Повертає індекс обраної дії або -1."""
        dlg = ThemedDialog(parent, title, kind="question", min_width=460, max_width=640)
        dlg.add_text(text)
        result = {"i": -1}
        dlg.add_button(cancel_text, key=-1)
        for i, label in enumerate(choices):
            dlg.add_button(
                label,
                primary=(i == 0),
                default=(i == 0),
                min_width=140,
                callback=(lambda idx=i: (result.__setitem__("i", idx), dlg.accept())),
            )
        dlg.exec()
        return result["i"]


class Input:
    """Drop-in заміна QInputDialog.getText."""

    @staticmethod
    def getText(parent, title, label, echo=QLineEdit.EchoMode.Normal, text="", placeholder="") -> tuple[str, bool]:
        dlg = ThemedDialog(parent, title, min_width=440, max_width=640)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        edit = QLineEdit(text)
        edit.setEchoMode(echo)
        edit.setPlaceholderText(placeholder)
        edit.selectAll()
        edit.returnPressed.connect(dlg.accept)
        dlg.body.addWidget(lbl)
        dlg.body.addWidget(edit)
        dlg.add_button("Скасувати")
        dlg.add_button("Гаразд", accept=True, primary=True, default=True)
        edit.setFocus()
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return edit.text(), ok
