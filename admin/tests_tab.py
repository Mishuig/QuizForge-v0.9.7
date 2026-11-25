"""
Вкладка «Тести» — створення/редагування тестів і питань.
Простий інтерфейс для нетехнічних користувачів.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QFrame,
    QGridLayout,
    QSizePolicy,
)

from core.db import Database
from core.dialogs import Msg, Input, ThemedDialog
from core.excel_import import generate_template, parse_excel, questions_to_db_payload
from core.models import QuestionType
from core.ui_kit import field

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OptionRow(QWidget):
    """Один рядок варіанту відповіді: текст + позначка «правильний»."""

    def __init__(self, text: str = "", is_correct: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("optionRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        self.correct_cb = QCheckBox()
        self.correct_cb.setChecked(is_correct)
        self.correct_cb.setToolTip("Правильна відповідь")
        self.correct_cb.setFixedWidth(28)

        self.text_edit = QLineEdit(text)
        self.text_edit.setPlaceholderText("Текст варіанту")
        self.text_edit.setMinimumHeight(40)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedSize(40, 40)
        self.remove_btn.setObjectName("dangerIconButton")
        self.remove_btn.setToolTip("Видалити варіант")

        self.expand_btn = QPushButton("✎")
        self.expand_btn.setFixedSize(40, 40)
        self.expand_btn.setObjectName("iconButton")
        self.expand_btn.setToolTip("Редагувати")
        self.expand_btn.clicked.connect(self._expand)

        layout.addWidget(self.correct_cb)
        layout.addWidget(self.text_edit, stretch=1)
        layout.addWidget(self.expand_btn)
        layout.addWidget(self.remove_btn)


    def _expand(self) -> None:
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Редагування варіанту")
        dlg.setMinimumSize(400, 200)
        lay = QVBoxLayout(dlg)
        edit = QTextEdit()
        edit.setPlainText(self.text_edit.text())
        lay.addWidget(edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec():
            self.text_edit.setText(edit.toPlainText())

    def get_data(self) -> tuple[str, bool]:
        return self.text_edit.text().strip(), self.correct_cb.isChecked()


class TestsTab(QWidget):
    """Вкладка керування тестами та питаннями."""

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._current_test_id: int | None = None
        self._current_question_id: int | None = None
        self._option_rows: list[OptionRow] = []
        self._building_ui = False

        self._build_ui()
        self._load_tests()

    # ------------------------------------------------------------------ UI
    @staticmethod
    def _button(text: str, name: str = "", height: int = 40) -> QPushButton:
        """Кнопка єдиної висоти; ширину задає сітка/розтягування."""
        btn = QPushButton(text)
        if name:
            btn.setObjectName(name)
        btn.setMinimumHeight(height)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 20)
        lay.setSpacing(14)
        return card, lay

    @staticmethod
    def _heading(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        title = QLabel("Тести")
        title.setObjectName("titleLabel")
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(20)
        root.addLayout(body, 1)

        # ================= Ліва колонка: список тестів =================
        sidebar, side = self._card()
        sidebar.setMinimumWidth(260)
        sidebar.setMaximumWidth(340)
        sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        side.addWidget(self._heading("Список тестів"))

        self.tests_list = QListWidget()
        self.tests_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tests_list.currentItemChanged.connect(self._on_test_selected)
        side.addWidget(self.tests_list, 1)

        self.btn_new_test = self._button("Новий тест", "primaryButton")
        self.btn_new_test.clicked.connect(self._new_test)
        self.btn_delete_test = self._button("Видалити", "dangerButton")
        self.btn_delete_test.clicked.connect(self._delete_test)
        self.btn_import = self._button("Імпорт з Excel", "secondaryButton")
        self.btn_import.clicked.connect(self._import_excel)
        self.btn_template = self._button("Шаблон", "secondaryButton")
        self.btn_template.clicked.connect(self._download_template)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.addWidget(self.btn_new_test, 0, 0)
        grid.addWidget(self.btn_delete_test, 0, 1)
        grid.addWidget(self.btn_import, 1, 0, 1, 2)
        grid.addWidget(self.btn_template, 2, 0, 1, 2)
        side.addLayout(grid)
        body.addWidget(sidebar)

        # ================= Права колонка: прокручувана область =================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 10, 0)
        col.setSpacing(16)
        scroll.setWidget(content)
        body.addWidget(scroll, 1)

        # ---------- Властивості тесту ----------
        props, pl = self._card()
        pl.addWidget(self._heading("Властивості тесту"))

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Назва тесту")

        self.time_spin = QSpinBox()
        self.time_spin.setRange(1, 600)
        self.time_spin.setValue(60)
        self.time_spin.setSuffix(" хв")

        self.pass_spin = QDoubleSpinBox()
        self.pass_spin.setRange(0, 100)
        self.pass_spin.setDecimals(1)
        self.pass_spin.setSuffix(" %")
        self.pass_spin.setSpecialValueText("Не задано")  # 0 трактуємо як «не задано»
        self.pass_spin.setValue(0)

        self.shuffle_q_cb = QCheckBox("Перемішувати питання")
        self.shuffle_o_cb = QCheckBox("Перемішувати варіанти")

        pg = QGridLayout()
        pg.setHorizontalSpacing(16)
        pg.setVerticalSpacing(14)
        pg.setColumnStretch(0, 1)
        pg.setColumnStretch(1, 1)
        pg.addWidget(field("Назва", self.title_edit), 0, 0, 1, 2)
        pg.addWidget(field("Ліміт часу", self.time_spin), 1, 0)
        pg.addWidget(field("Прохідний бал", self.pass_spin), 1, 1)
        pl.addLayout(pg)

        checks = QHBoxLayout()
        checks.setSpacing(28)
        checks.addWidget(self.shuffle_q_cb)
        checks.addWidget(self.shuffle_o_cb)
        checks.addStretch(1)
        pl.addLayout(checks)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_test_btn = self._button("Зберегти", "primaryButton")
        save_test_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        save_test_btn.setMinimumWidth(230)
        save_test_btn.clicked.connect(self._save_test_props)
        save_row.addWidget(save_test_btn)
        pl.addLayout(save_row)
        col.addWidget(props)

        # ---------- Питання ----------
        qcard, ql = self._card()
        ql.addWidget(self._heading("Питання"))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        ql.addWidget(splitter)

        # --- список питань + керування
        q_left = QVBoxLayout()
        q_left.setSpacing(12)
        self.questions_list = QListWidget()
        self.questions_list.setMinimumHeight(280)
        self.questions_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.questions_list.currentItemChanged.connect(self._on_question_selected)
        q_left.addWidget(self.questions_list, 1)

        self.btn_q_up = self._button("↑ Вище", "secondaryButton", height=40)
        self.btn_q_up.clicked.connect(lambda: self._move_question(-1))
        self.btn_q_down = self._button("↓ Нижче", "secondaryButton", height=40)
        self.btn_q_down.clicked.connect(lambda: self._move_question(1))
        self.btn_add_q = self._button("Додати питання", "primaryButton", height=40)
        self.btn_add_q.clicked.connect(self._add_question)
        self.btn_del_q = self._button("Видалити", "dangerButton", height=40)
        self.btn_del_q.clicked.connect(self._delete_question)

        qb = QGridLayout()
        qb.setHorizontalSpacing(10)
        qb.setVerticalSpacing(10)
        qb.setColumnStretch(0, 1)
        qb.setColumnStretch(1, 1)
        qb.addWidget(self.btn_q_up, 0, 0)
        qb.addWidget(self.btn_q_down, 0, 1)
        qb.addWidget(self.btn_add_q, 1, 0)
        qb.addWidget(self.btn_del_q, 1, 1)
        q_left.addLayout(qb)
        left_w = QWidget()
        left_w.setLayout(q_left)
        left_w.setMinimumWidth(200)
        splitter.addWidget(left_w)

        # --- редактор питання
        q_right = QVBoxLayout()
        q_right.setSpacing(14)

        self.q_text = QTextEdit()
        self.q_text.setPlaceholderText("Текст питання")
        self.q_text.setMinimumHeight(70)
        q_right.addWidget(field("Текст питання", self.q_text))

        self.q_type = QComboBox()
        self.q_type.addItem("Одна правильна (single)", QuestionType.SINGLE.value)
        self.q_type.addItem("Кілька правильних (multiple)", QuestionType.MULTIPLE.value)
        self.q_type.addItem("Відкрита відповідь (open)", QuestionType.OPEN.value)
        self.q_type.currentIndexChanged.connect(self._on_type_changed)

        self.q_points = QDoubleSpinBox()
        self.q_points.setRange(0.01, 1000)
        self.q_points.setDecimals(2)
        self.q_points.setSingleStep(0.25)
        self.q_points.setValue(1.0)
        self.q_points.setToolTip(
            "Бали за питання. Можна дробові: 0.25, 0.5, 1.5 тощо.\n"
            "Для multiple при partial_credit=true бал ділиться пропорційно між правильними."
        )
        tp = QGridLayout()
        tp.setHorizontalSpacing(16)
        tp.setColumnStretch(0, 3)
        tp.setColumnStretch(1, 1)
        tp.addWidget(field("Тип питання", self.q_type), 0, 0)
        tp.addWidget(field("Бали", self.q_points), 0, 1)
        q_right.addLayout(tp)

        self.type_hint = QLabel()
        self.type_hint.setObjectName("hintLabel")
        self.type_hint.setWordWrap(True)
        q_right.addWidget(self.type_hint)

        # Варіанти (single/multiple) — без вкладеної прокрутки: скролиться вся сторінка
        self.options_group = QWidget()
        og = QVBoxLayout(self.options_group)
        og.setContentsMargins(0, 0, 0, 0)
        og.setSpacing(12)
        cap = QLabel("Варіанти відповідей")
        cap.setObjectName("fieldLabel")
        og.addWidget(cap)
        options_scroll = QScrollArea()
        options_scroll.setWidgetResizable(True)
        options_scroll.setFrameShape(QFrame.Shape.NoFrame)
        options_scroll.setMinimumHeight(100)  # ~2 rows
        options_scroll.setMaximumHeight(400)  # grow until needed
        holder = QWidget()
        self.options_container = QVBoxLayout(holder)
        self.options_container.setContentsMargins(0, 0, 0, 0)
        self.options_container.setSpacing(12)
        options_scroll.setWidget(holder)
        og.addWidget(options_scroll)
        self._options_scroll = options_scroll
        add_opt_btn = self._button("+ Додати варіант")
        add_opt_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        add_opt_btn.setMinimumWidth(180)
        add_opt_btn.clicked.connect(lambda _checked=False: self._add_option_row(focus=True))
        og.addWidget(add_opt_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        q_right.addWidget(self.options_group)

        # Відкриті відповіді
        self.open_group = QWidget()
        og2 = QVBoxLayout(self.open_group)
        og2.setContentsMargins(0, 0, 0, 0)
        og2.setSpacing(12)
        self.open_answers_edit = QLineEdit()
        self.open_answers_edit.setPlaceholderText("наприклад: Київ; Kyiv; Київ місто")
        og2.addWidget(field("Допустимі відповіді (через «;»)", self.open_answers_edit))
        hint = QLabel("Без урахування регістру і пробілів.")
        hint.setObjectName("subtitleLabel")
        og2.addWidget(hint)
        q_right.addWidget(self.open_group)
        self.open_group.hide()

        q_right.addStretch(1)
        save_q_row = QHBoxLayout()
        save_q_row.addStretch(1)
        self.btn_save_q = self._button("Зберегти питання", "primaryButton")
        self.btn_save_q.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.btn_save_q.setMinimumWidth(230)
        self.btn_save_q.clicked.connect(self._save_question)
        save_q_row.addWidget(self.btn_save_q)
        q_right.addLayout(save_q_row)

        right_w = QWidget()
        right_w.setLayout(q_right)
        right_w.setMinimumWidth(300)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        col.addWidget(qcard)
        col.addStretch(1)

        self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool) -> None:
        for w in (
            self.title_edit,
            self.time_spin,
            self.shuffle_q_cb,
            self.shuffle_o_cb,
            self.pass_spin,
            self.questions_list,
            self.btn_add_q,
            self.btn_del_q,
            self.btn_q_up,
            self.btn_q_down,
            self.q_text,
            self.q_type,
            self.q_points,
            self.btn_save_q,
            self.options_group,
            self.open_group,
        ):
            w.setEnabled(enabled)
        self.btn_delete_test.setEnabled(enabled and self._current_test_id is not None)

    # ------------------------------------------------------------------ Тести
    def _load_tests(self) -> None:
        self.tests_list.clear()
        rows = self.db.fetchall(
            "SELECT id, title FROM tests ORDER BY title COLLATE NOCASE"
        )
        for row in rows:
            item = QListWidgetItem(row["title"])
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.tests_list.addItem(item)

    def _on_test_selected(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            self._current_test_id = None
            self._set_editor_enabled(False)
            self.questions_list.clear()
            return

        test_id = current.data(Qt.ItemDataRole.UserRole)
        self._current_test_id = test_id
        self._set_editor_enabled(True)
        self._load_test_props(test_id)
        self._load_questions(test_id)
        self._clear_question_editor()

    def _load_test_props(self, test_id: int) -> None:
        row = self.db.fetchone("SELECT * FROM tests WHERE id = ?", (test_id,))
        if not row:
            return
        self.title_edit.setText(row["title"])
        self.time_spin.setValue(row["time_limit_minutes"])
        self.shuffle_q_cb.setChecked(bool(row["shuffle_questions"]))
        self.shuffle_o_cb.setChecked(bool(row["shuffle_options"]))
        pass_pct = row["pass_percent"]
        self.pass_spin.setValue(float(pass_pct) if pass_pct is not None else 0.0)

    def _new_test(self) -> None:
        title, ok = Input.getText(self, "Новий тест", "Назва тесту:")
        if not ok or not title.strip():
            return
        title = title.strip()
        test_id = self.db.insert(
            "tests",
            {
                "title": title,
                "time_limit_minutes": 60,
                "violation_threshold": 5,
                "shuffle_questions": 0,
                "shuffle_options": 0,
                "pass_percent": None,
                "created_at": _utc_now(),
            },
        )
        self.db.log_audit("test_created", "admin", f"id={test_id}, title={title}")
        self._load_tests()
        # Вибрати щойно створений
        for i in range(self.tests_list.count()):
            item = self.tests_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == test_id:
                self.tests_list.setCurrentItem(item)
                break

    def _save_test_props(self) -> None:
        if self._current_test_id is None:
            return
        title = self.title_edit.text().strip()
        if not title:
            Msg.warning(self, "Помилка", "Вкажіть назву тесту.")
            return

        pass_val = self.pass_spin.value()
        pass_percent = pass_val if pass_val > 0 else None

        self.db.update(
            "tests",
            {
                "title": title,
                "time_limit_minutes": self.time_spin.value(),
                "shuffle_questions": 1 if self.shuffle_q_cb.isChecked() else 0,
                "shuffle_options": 1 if self.shuffle_o_cb.isChecked() else 0,
                "pass_percent": pass_percent,
            },
            "id = ?",
            (self._current_test_id,),
        )
        self.db.log_audit(
            "test_updated", "admin", f"id={self._current_test_id}, title={title}"
        )
        # Оновити назву в списку
        item = self.tests_list.currentItem()
        if item:
            item.setText(title)
        Msg.information(self, "Збережено", "Властивості тесту збережено.")

    def _delete_test(self) -> None:
        if self._current_test_id is None:
            return
        reply = Msg.question(
            self,
            "Підтвердження",
            "Видалити тест разом із усіма питаннями?\nЦю дію неможливо скасувати.",
            Msg.StandardButton.Yes | Msg.StandardButton.No,
            Msg.StandardButton.No,
        )
        if reply != Msg.StandardButton.Yes:
            return
        tid = self._current_test_id
        self.db.execute("DELETE FROM tests WHERE id = ?", (tid,))
        self.db.log_audit("test_deleted", "admin", f"id={tid}")
        self._current_test_id = None
        self._load_tests()
        self._set_editor_enabled(False)
        self.questions_list.clear()
        self._clear_question_editor()

    # ------------------------------------------------------------------ Питання
    def _load_questions(self, test_id: int) -> None:
        self.questions_list.clear()
        rows = self.db.fetchall(
            "SELECT id, text, qtype, points, order_index FROM questions "
            "WHERE test_id = ? ORDER BY order_index, id",
            (test_id,),
        )
        for i, row in enumerate(rows, start=1):
            preview = (row["text"] or "")[:60]
            if len(row["text"] or "") > 60:
                preview += "…"
            label = f"{i}. [{row['qtype']}] {preview}  ({row['points']} б.)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.questions_list.addItem(item)

    def _on_question_selected(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None or self._current_test_id is None:
            self._current_question_id = None
            self._clear_question_editor()
            return
        qid = current.data(Qt.ItemDataRole.UserRole)
        self._current_question_id = qid
        self._load_question(qid)

    def _clear_question_editor(self) -> None:
        self._current_question_id = None
        self.q_text.clear()
        self.q_type.setCurrentIndex(0)
        self.q_points.setValue(1.0)
        self.open_answers_edit.clear()
        self._clear_option_rows()
        self._on_type_changed()

    def _load_question(self, question_id: int) -> None:
        row = self.db.fetchone("SELECT * FROM questions WHERE id = ?", (question_id,))
        if not row:
            return
        self.q_text.setPlainText(row["text"])
        idx = self.q_type.findData(row["qtype"])
        if idx >= 0:
            self.q_type.setCurrentIndex(idx)
        self.q_points.setValue(float(row["points"]))
        self.open_answers_edit.setText(row["open_answers"] or "")

        self._clear_option_rows()
        if row["qtype"] in (QuestionType.SINGLE.value, QuestionType.MULTIPLE.value):
            opts = self.db.fetchall(
                "SELECT text, is_correct FROM options "
                "WHERE question_id = ? ORDER BY order_index, id",
                (question_id,),
            )
            for opt in opts:
                self._add_option_row(opt["text"], bool(opt["is_correct"]))
        self._on_type_changed()

    def _on_type_changed(self) -> None:
        qtype = self.q_type.currentData()
        is_open = qtype == QuestionType.OPEN.value
        self.options_group.setVisible(not is_open)
        self.open_group.setVisible(is_open)

        # Правила для кожного типу
        if qtype == QuestionType.SINGLE.value:
            self.type_hint.setText(
                "Правила (одна правильна):\n"
                "• Мінімум 2 варіанти відповіді.\n"
                "• Позначте рівно ОДИН правильний варіант галочкою.\n"
                "• Бал нараховується лише за вибір саме цього варіанту.\n"
                "• Бали можна дробові: 0.25, 0.5, 1.5 тощо."
            )
        elif qtype == QuestionType.MULTIPLE.value:
            self.type_hint.setText(
                "Правила (кілька правильних):\n"
                "• Мінімум 2 варіанти. Позначте всі правильні галочками.\n"
                "• partial_credit = false (за замовчуванням): бал лише за "
                "повністю правильний набір (усі потрібні + жоден зайвий).\n"
                "• partial_credit = true (config.json): кожна правильна відповідь "
                "оцінюється пропорційно — (кількість вірно вибраних / кількість "
                "правильних) × бали питання. Без штрафів за зайві.\n"
                "• Бали можна дробові: 0.25, 0.5, 1.5 тощо."
            )
        else:  # open
            self.type_hint.setText(
                "Правила (відкрита відповідь):\n"
                "• Варіанти не потрібні — заповніть поле «Допустимі відповіді».\n"
                "• Кілька допустимих відповідей через «;» (напр. Київ; Kyiv).\n"
                "• Без урахування регістру і пробілів.\n"
                "• Бал нараховується, якщо відповідь збігається з будь-якою допустимою.\n"
                "• Бали можна дробові: 0.25, 0.5, 1.5 тощо."
            )

    def _clear_option_rows(self) -> None:
        for row in self._option_rows:
            self.options_container.removeWidget(row)
            row.deleteLater()
        self._option_rows.clear()

    def _add_option_row(self, text: str = "", is_correct: bool = False, focus: bool = False) -> None:
        # Захист від сигналу clicked(bool): текст завжди рядок
        text = text if isinstance(text, str) else ""
        row = OptionRow(text, bool(is_correct))
        row.remove_btn.clicked.connect(lambda _checked=False, r=row: self._remove_option_row(r))
        self._option_rows.append(row)
        self.options_container.addWidget(row)
        if focus:
            row.text_edit.setFocus()
        if hasattr(self, "_options_scroll"):
            self._options_scroll.ensureWidgetVisible(row)

    def _remove_option_row(self, row: OptionRow) -> None:
        if row in self._option_rows:
            self._option_rows.remove(row)
            self.options_container.removeWidget(row)
            row.deleteLater()

    def _add_question(self) -> None:
        if self._current_test_id is None:
            return
        # Створюємо порожнє питання з наступним order_index
        max_order = self.db.fetchone(
            "SELECT COALESCE(MAX(order_index), -1) AS m FROM questions WHERE test_id = ?",
            (self._current_test_id,),
        )
        next_order = (max_order["m"] if max_order else -1) + 1

        qid = self.db.insert(
            "questions",
            {
                "test_id": self._current_test_id,
                "text": "Нове питання",
                "qtype": QuestionType.SINGLE.value,
                "points": 1.0,
                "order_index": next_order,
                "open_answers": "",
            },
        )
        # Два порожні варіанти за замовчуванням
        for i, txt in enumerate(("Варіант 1", "Варіант 2")):
            self.db.insert(
                "options",
                {
                    "question_id": qid,
                    "text": txt,
                    "is_correct": 1 if i == 0 else 0,
                    "order_index": i,
                },
            )
        self.db.log_audit("question_created", "admin", f"id={qid}, test_id={self._current_test_id}")
        self._load_questions(self._current_test_id)
        # Вибрати нове
        for i in range(self.questions_list.count()):
            item = self.questions_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == qid:
                self.questions_list.setCurrentItem(item)
                break

    def _save_question(self) -> None:
        if self._current_test_id is None or self._current_question_id is None:
            Msg.warning(self, "Помилка", "Спочатку виберіть або створіть питання.")
            return

        text = self.q_text.toPlainText().strip()
        if not text:
            Msg.warning(self, "Помилка", "Текст питання не може бути порожнім.")
            return

        qtype = self.q_type.currentData()
        points = self.q_points.value()

        if qtype == QuestionType.OPEN.value:
            open_answers = self.open_answers_edit.text().strip()
            if not open_answers:
                Msg.warning(
                    self, "Помилка", "Вкажіть хоча б одну допустиму відповідь (через «;»)."
                )
                return
            # Зберігаємо питання, видаляємо варіанти
            self.db.update(
                "questions",
                {
                    "text": text,
                    "qtype": qtype,
                    "points": points,
                    "open_answers": open_answers,
                },
                "id = ?",
                (self._current_question_id,),
            )
            self.db.execute(
                "DELETE FROM options WHERE question_id = ?", (self._current_question_id,)
            )
        else:
            # single / multiple
            options_data: list[tuple[str, bool]] = []
            for row in self._option_rows:
                t, correct = row.get_data()
                if t:
                    options_data.append((t, correct))

            if len(options_data) < 2:
                Msg.warning(
                    self, "Помилка", "Для цього типу потрібно щонайменше 2 варіанти."
                )
                return
            correct_count = sum(1 for _, c in options_data if c)
            if correct_count == 0:
                Msg.warning(self, "Помилка", "Позначте хоча б один правильний варіант.")
                return
            if qtype == QuestionType.SINGLE.value and correct_count > 1:
                Msg.warning(
                    self,
                    "Помилка",
                    "Для типу «Одна правильна» можна позначити лише один варіант.",
                )
                return

            self.db.update(
                "questions",
                {
                    "text": text,
                    "qtype": qtype,
                    "points": points,
                    "open_answers": "",
                },
                "id = ?",
                (self._current_question_id,),
            )
            # Перезапис варіантів
            self.db.execute(
                "DELETE FROM options WHERE question_id = ?", (self._current_question_id,)
            )
            for i, (t, correct) in enumerate(options_data):
                self.db.insert(
                    "options",
                    {
                        "question_id": self._current_question_id,
                        "text": t,
                        "is_correct": 1 if correct else 0,
                        "order_index": i,
                    },
                )

        self.db.log_audit(
            "question_updated",
            "admin",
            f"id={self._current_question_id}, test_id={self._current_test_id}",
        )
        self._load_questions(self._current_test_id)
        # Повернути виділення
        for i in range(self.questions_list.count()):
            item = self.questions_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self._current_question_id:
                self.questions_list.setCurrentItem(item)
                break
        Msg.information(self, "Збережено", "Питання збережено.")

    def _delete_question(self) -> None:
        if self._current_question_id is None or self._current_test_id is None:
            return
        reply = Msg.question(
            self,
            "Підтвердження",
            "Видалити це питання?",
            Msg.StandardButton.Yes | Msg.StandardButton.No,
            Msg.StandardButton.No,
        )
        if reply != Msg.StandardButton.Yes:
            return
        qid = self._current_question_id
        self.db.execute("DELETE FROM questions WHERE id = ?", (qid,))
        self.db.log_audit("question_deleted", "admin", f"id={qid}")
        self._current_question_id = None
        self._load_questions(self._current_test_id)
        self._clear_question_editor()

    def _move_question(self, direction: int) -> None:
        """direction: -1 вгору, +1 вниз."""
        if self._current_test_id is None or self._current_question_id is None:
            return
        rows = self.db.fetchall(
            "SELECT id, order_index FROM questions WHERE test_id = ? ORDER BY order_index, id",
            (self._current_test_id,),
        )
        ids = [r["id"] for r in rows]
        try:
            idx = ids.index(self._current_question_id)
        except ValueError:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(ids):
            return
        # Міняємо order_index місцями
        other_id = ids[new_idx]
        order_a = rows[idx]["order_index"]
        order_b = rows[new_idx]["order_index"]
        # Якщо однакові — робимо унікальними
        if order_a == order_b:
            order_b = order_a + direction

        self.db.update("questions", {"order_index": order_b}, "id = ?", (self._current_question_id,))
        self.db.update("questions", {"order_index": order_a}, "id = ?", (other_id,))

        # Нормалізація order_index (0,1,2,...)
        rows2 = self.db.fetchall(
            "SELECT id FROM questions WHERE test_id = ? ORDER BY order_index, id",
            (self._current_test_id,),
        )
        for i, r in enumerate(rows2):
            self.db.update("questions", {"order_index": i}, "id = ?", (r["id"],))

        self._load_questions(self._current_test_id)
        for i in range(self.questions_list.count()):
            item = self.questions_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self._current_question_id:
                self.questions_list.setCurrentItem(item)
                break

    # ------------------------------------------------------------------ Імпорт Excel
    def _download_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Зберегти шаблон",
            "шаблон_тест.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            generate_template(path)
            Msg.information(
                self,
                "Шаблон",
                f"Шаблон збережено:\n{path}\n\n"
                "Відкрийте файл, заповніть аркуш «Питання» і імпортуйте його.",
            )
        except Exception as exc:
            logger.exception("Помилка створення шаблону")
            Msg.critical(self, "Помилка", f"Не вдалося створити шаблон:\n{exc}")

    def _import_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Виберіть файл Excel",
            "",
            "Excel (*.xlsx)",
        )
        if not path:
            return

        try:
            result = parse_excel(path)
        except Exception as exc:
            logger.exception("Помилка читання Excel")
            Msg.critical(self, "Помилка", f"Не вдалося прочитати файл:\n{exc}")
            return

        if result.errors:
            self._show_import_errors(result.errors)
            return

        if not result.questions:
            Msg.warning(self, "Імпорт", "У файлі не знайдено питань.")
            return

        # Підсумок + підтвердження + вибір цілі
        summary = (
            f"Знайдено {len(result.questions)} питань, "
            f"сума балів {result.total_points:g}.\n\n"
            "Куди імпортувати?"
        )
        choice = Msg.choice(
            self,
            "Підтвердити імпорт",
            summary,
            ["Створити новий тест", "Додати до вибраного"],
        )
        if choice == 0:
            title, ok = Input.getText(
                self, "Новий тест", "Назва нового тесту:", text=Path(path).stem
            )
            if not ok or not title.strip():
                return
            test_id = self.db.insert(
                "tests",
                {
                    "title": title.strip(),
                    "time_limit_minutes": 60,
                    "violation_threshold": 5,
                    "shuffle_questions": 0,
                    "shuffle_options": 0,
                    "pass_percent": None,
                    "created_at": _utc_now(),
                },
            )
            self._insert_questions(test_id, result.questions)
            self.db.log_audit(
                "test_imported",
                "admin",
                f"new test_id={test_id}, questions={len(result.questions)}, file={path}",
            )
            self._load_tests()
            for i in range(self.tests_list.count()):
                item = self.tests_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == test_id:
                    self.tests_list.setCurrentItem(item)
                    break
            Msg.information(
                self, "Імпорт", f"Створено тест «{title.strip()}» з {len(result.questions)} питаннями."
            )
        elif choice == 1:
            if self._current_test_id is None:
                Msg.warning(
                    self, "Імпорт", "Спочатку виберіть тест у списку зліва."
                )
                return
            self._insert_questions(self._current_test_id, result.questions)
            self.db.log_audit(
                "questions_imported",
                "admin",
                f"test_id={self._current_test_id}, questions={len(result.questions)}, file={path}",
            )
            self._load_questions(self._current_test_id)
            Msg.information(
                self,
                "Імпорт",
                f"Додано {len(result.questions)} питань до поточного тесту.",
            )

    def _show_import_errors(self, errors: list) -> None:
        dlg = ThemedDialog(
            self,
            "Помилки імпорту",
            "Імпорт не виконано. Виправте помилки у файлі та спробуйте знову.",
            kind="warning",
            min_width=560,
            max_width=900,
        )
        dlg.setMinimumHeight(360)
        dlg.resize(680, 440)

        table = QTableWidget(len(errors), 2)
        table.setHorizontalHeaderLabels(["Рядок", "Що не так"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setWordWrap(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        for i, err in enumerate(errors):
            row_label = str(err.row) if err.row else "—"
            table.setItem(i, 0, QTableWidgetItem(row_label))
            table.setItem(i, 1, QTableWidgetItem(err.message))
        table.resizeRowsToContents()
        dlg.body.addWidget(table, 1)

        dlg.add_button("Зрозуміло", accept=True, primary=True, default=True)
        dlg.exec()

    def _insert_questions(self, test_id: int, questions) -> None:
        """Вставляє розпарсені питання в БД для вказаного тесту."""
        max_order_row = self.db.fetchone(
            "SELECT COALESCE(MAX(order_index), -1) AS m FROM questions WHERE test_id = ?",
            (test_id,),
        )
        next_order = (max_order_row["m"] if max_order_row else -1) + 1

        payload = questions_to_db_payload(questions)
        for item in payload:
            qid = self.db.insert(
                "questions",
                {
                    "test_id": test_id,
                    "text": item["text"],
                    "qtype": item["qtype"],
                    "points": item["points"],
                    "order_index": next_order,
                    "open_answers": item["open_answers"],
                },
            )
            next_order += 1
            for opt in item["options"]:
                self.db.insert(
                    "options",
                    {
                        "question_id": qid,
                        "text": opt["text"],
                        "is_correct": 1 if opt["is_correct"] else 0,
                        "order_index": opt["order_index"],
                    },
                )
