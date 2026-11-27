"""
Вкладка «Тести» — створення/редагування тестів і питань.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QRadioButton, QButtonGroup, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QScrollArea, QSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget, QFrame, QGridLayout,
)

from core.db import Database
from core.dialogs import Msg
from core.excel_import import generate_template, parse_excel, questions_to_db_payload
from core.models import QuestionType
from core.ui_kit import field, icon_button, button_row, AdaptiveLabel

logger = logging.getLogger(__name__)


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class OptionRow(QWidget):
    def __init__(self, text="", is_correct=False, is_single=False, parent=None):
        super().__init__(parent)
        self.setObjectName("optionRow")
        self.setMinimumHeight(44)
        self._is_single = is_single
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        
        if is_single:
            self.correct_widget = QRadioButton()
            self.correct_widget.setToolTip("Правильна відповідь (одна)")
        else:
            self.correct_widget = QCheckBox()
            self.correct_widget.setToolTip("Правильна відповідь")
        self.correct_widget.setChecked(is_correct)
        self.correct_widget.setFixedWidth(24)
        
        self.text_edit = QLineEdit(text)
        self.text_edit.setPlaceholderText("Текст варіанту")
        self.text_edit.setMinimumHeight(36)
        self.remove_btn = icon_button("fa5s.times", "Видалити", "#F87171", size=14, danger=True)
        self.expand_btn = icon_button("fa5s.edit", "Редагувати", size=14)
        self.expand_btn.clicked.connect(self._expand)
        layout.addWidget(self.correct_widget)
        layout.addWidget(self.text_edit, stretch=1)
        layout.addWidget(self.expand_btn)
        layout.addWidget(self.remove_btn)

    def _expand(self):
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

    def get_data(self):
        try:
            return self.text_edit.text().strip(), self.correct_widget.isChecked()
        except RuntimeError:
            return "", False

    def set_checked(self, checked: bool):
        try:
            self.correct_widget.setChecked(checked)
        except RuntimeError:
            pass

    def is_checked(self) -> bool:
        try:
            return self.correct_widget.isChecked()
        except RuntimeError:
            return False


class TestsTab(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._current_test_id = None
        self._current_question_id = None
        self._option_rows = []
        self._radio_group = None
        self._build_ui()
        self._load_tests()

    @staticmethod
    def _card():
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(12)
        return card, lay

    @staticmethod
    def _heading(text):
        lbl = AdaptiveLabel(text, max_font=14, min_font=10)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        title = AdaptiveLabel("Тести", max_font=22, min_font=14)
        title.setObjectName("titleLabel")
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        sidebar, side = self._card()
        sidebar.setMinimumWidth(160)
        sidebar.setMaximumWidth(240)
        side.addWidget(self._heading("Список тестів"))
        self.tests_list = QListWidget()
        self.tests_list.setMinimumHeight(100)
        self.tests_list.currentItemChanged.connect(self._on_test_selected)
        side.addWidget(self.tests_list, 1)

        self.btn_new_test = icon_button("fa5s.plus", "Новий тест", "#3b82f6", accent=True)
        self.btn_new_test.clicked.connect(self._new_test)
        self.btn_delete_test = icon_button("fa5s.trash", "Видалити", "#F87171", danger=True)
        self.btn_delete_test.clicked.connect(self._delete_test)
        self.btn_import = icon_button("fa5s.file-import", "Імпорт")
        self.btn_import.clicked.connect(self._import_excel)
        self.btn_template = icon_button("fa5s.file-download", "Шаблон")
        self.btn_template.clicked.connect(self._download_template)
        side.addWidget(button_row(self.btn_new_test, self.btn_delete_test, self.btn_import, self.btn_template))
        body.addWidget(sidebar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(12)
        scroll.setWidget(content)
        body.addWidget(scroll, 1)

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
        self.shuffle_q_cb = QCheckBox("Перемішувати питання")
        self.shuffle_o_cb = QCheckBox("Перемішувати варіанти")

        pg = QGridLayout()
        pg.setSpacing(8)
        pg.addWidget(field("Назва", self.title_edit), 0, 0, 1, 2)
        pg.addWidget(field("Ліміт часу", self.time_spin), 1, 0)
        pg.addWidget(field("Прохідний бал", self.pass_spin), 1, 1)
        pl.addLayout(pg)
        checks = QHBoxLayout()
        checks.addWidget(self.shuffle_q_cb)
        checks.addWidget(self.shuffle_o_cb)
        checks.addStretch(1)
        pl.addLayout(checks)

        save_test_btn = icon_button("fa5s.save", "Зберегти", "#3b82f6", accent=True)
        save_test_btn.clicked.connect(self._save_test_props)
        pl.addWidget(button_row(save_test_btn), alignment=Qt.AlignmentFlag.AlignRight)
        col.addWidget(props)

        qcard, ql = self._card()
        ql.addWidget(self._heading("Питання"))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        ql.addWidget(splitter)

        q_left = QVBoxLayout()
        q_left.setSpacing(8)
        self.questions_list = QListWidget()
        self.questions_list.setMinimumHeight(120)
        self.questions_list.currentItemChanged.connect(self._on_question_selected)
        q_left.addWidget(self.questions_list, 1)

        self.btn_q_up = icon_button("fa5s.arrow-up", "Вище")
        self.btn_q_up.clicked.connect(lambda: self._move_question(-1))
        self.btn_q_down = icon_button("fa5s.arrow-down", "Нижче")
        self.btn_q_down.clicked.connect(lambda: self._move_question(1))
        self.btn_add_q = icon_button("fa5s.plus-circle", "Додати питання", "#3b82f6", accent=True)
        self.btn_add_q.clicked.connect(self._add_question)
        self.btn_del_q = icon_button("fa5s.trash", "Видалити питання", "#F87171", danger=True)
        self.btn_del_q.clicked.connect(self._delete_question)
        q_left.addWidget(button_row(self.btn_q_up, self.btn_q_down, self.btn_add_q, self.btn_del_q))

        left_w = QWidget()
        left_w.setLayout(q_left)
        left_w.setMinimumWidth(140)
        splitter.addWidget(left_w)

        q_right = QVBoxLayout()
        q_right.setSpacing(10)
        # Питання — 2 рядки + олівець для розгортання
        q_row = QHBoxLayout()
        q_row.setSpacing(4)
        self.q_text = QTextEdit()
        self.q_text.setPlaceholderText("Текст питання")
        self.q_text.setMaximumHeight(56)
        self.q_text.setMinimumHeight(44)
        q_row.addWidget(self.q_text, stretch=1)
        self.q_expand_btn = icon_button("fa5s.edit", "Редагувати", size=14)
        self.q_expand_btn.clicked.connect(self._expand_question)
        q_row.addWidget(self.q_expand_btn)
        q_right.addWidget(field("Текст питання", q_row))

        self.q_type = QComboBox()
        self.q_type.addItem("Одна правильна", QuestionType.SINGLE.value)
        self.q_type.addItem("Кілька правильних", QuestionType.MULTIPLE.value)
        self.q_type.addItem("Відкрита відповідь", QuestionType.OPEN.value)
        self.q_type.currentIndexChanged.connect(self._on_type_changed)

        self.q_points = QDoubleSpinBox()
        self.q_points.setRange(0.01, 1000)
        self.q_points.setDecimals(2)
        self.q_points.setValue(1.0)

        tp = QGridLayout()
        tp.setSpacing(8)
        tp.addWidget(field("Тип", self.q_type), 0, 0)
        tp.addWidget(field("Бали", self.q_points), 0, 1)
        q_right.addLayout(tp)

        self.type_hint = QLabel()
        self.type_hint.setObjectName("hintLabel")
        self.type_hint.setWordWrap(True)
        q_right.addWidget(self.type_hint)

        self.options_group = QWidget()
        og = QVBoxLayout(self.options_group)
        og.setContentsMargins(0, 0, 0, 0)
        og.setSpacing(8)
        cap = QLabel("Варіанти відповідей")
        cap.setObjectName("fieldLabel")
        og.addWidget(cap)
        options_scroll = QScrollArea()
        options_scroll.setWidgetResizable(True)
        options_scroll.setMinimumHeight(80)
        options_scroll.setMaximumHeight(300)
        holder = QWidget()
        self.options_container = QVBoxLayout(holder)
        self.options_container.setSpacing(6)
        options_scroll.setWidget(holder)
        og.addWidget(options_scroll)
        self._options_scroll = options_scroll
        add_opt_btn = icon_button("fa5s.plus", "Додати варіант")
        add_opt_btn.clicked.connect(lambda: self._add_option_row(focus=True))
        og.addWidget(button_row(add_opt_btn))
        q_right.addWidget(self.options_group)

        self.open_group = QWidget()
        og2 = QVBoxLayout(self.open_group)
        og2.setContentsMargins(0, 0, 0, 0)
        self.open_answers_edit = QLineEdit()
        self.open_answers_edit.setPlaceholderText("Київ; Kyiv")
        og2.addWidget(field("Допустимі відповіді", self.open_answers_edit))
        q_right.addWidget(self.open_group)
        self.open_group.hide()

        q_right.addStretch(1)
        self.btn_save_q = icon_button("fa5s.save", "Зберегти питання", "#3b82f6", accent=True)
        self.btn_save_q.clicked.connect(self._save_question)
        q_right.addWidget(button_row(self.btn_save_q), alignment=Qt.AlignmentFlag.AlignRight)

        right_w = QWidget()
        right_w.setLayout(q_right)
        right_w.setMinimumWidth(200)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        col.addWidget(qcard)
        col.addStretch(1)

        self._set_editor_enabled(False)

    def _is_single_type(self) -> bool:
        try:
            return self.q_type.currentData() == QuestionType.SINGLE.value
        except RuntimeError:
            return False

    def _set_editor_enabled(self, enabled):
        for w in (self.title_edit, self.time_spin, self.shuffle_q_cb, self.shuffle_o_cb, self.pass_spin,
                  self.questions_list, self.btn_add_q, self.btn_del_q, self.btn_q_up, self.btn_q_down,
                  self.q_text, self.q_type, self.q_points, self.btn_save_q, self.options_group, self.open_group):
            try:
                w.setEnabled(enabled)
            except RuntimeError:
                pass
        try:
            self.btn_delete_test.setEnabled(enabled and self._current_test_id is not None)
        except RuntimeError:
            pass

    def _load_tests(self):
        self.tests_list.clear()
        rows = self.db.fetchall("SELECT id, title FROM tests ORDER BY title")
        for row in rows:
            item = QListWidgetItem(row["title"])
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.tests_list.addItem(item)

    def _on_test_selected(self, current, _prev):
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

    def _load_test_props(self, test_id):
        row = self.db.fetchone("SELECT * FROM tests WHERE id = ?", (test_id,))
        if not row:
            return
        self.title_edit.setText(row["title"])
        self.time_spin.setValue(row["time_limit_minutes"])
        self.shuffle_q_cb.setChecked(bool(row["shuffle_questions"]))
        self.shuffle_o_cb.setChecked(bool(row["shuffle_options"]))
        self.pass_spin.setValue(float(row["pass_percent"] or 0))

    def _new_test(self):
        title, ok = Msg.getText(self, "Новий тест", "Назва:")
        if not ok or not title.strip():
            return
        tid = self.db.insert("tests", {"title": title.strip(), "time_limit_minutes": 60, "created_at": _utc_now()})
        self._load_tests()
        for i in range(self.tests_list.count()):
            if self.tests_list.item(i).data(Qt.ItemDataRole.UserRole) == tid:
                self.tests_list.setCurrentRow(i)
                break

    def _delete_test(self):
        if not self._current_test_id:
            return
        if Msg.question(self, "Видалити", "Видалити тест?") != Msg.StandardButton.Yes:
            return
        self.db.execute("DELETE FROM tests WHERE id = ?", (self._current_test_id,))
        self._current_test_id = None
        self._load_tests()

    def _save_test_props(self):
        if not self._current_test_id:
            return
        self.db.update("tests", {
            "title": self.title_edit.text().strip(),
            "time_limit_minutes": self.time_spin.value(),
            "shuffle_questions": int(self.shuffle_q_cb.isChecked()),
            "shuffle_options": int(self.shuffle_o_cb.isChecked()),
            "pass_percent": self.pass_spin.value() or None,
        }, "id = ?", (self._current_test_id,))
        self._load_tests()

    def _load_questions(self, test_id):
        self.questions_list.clear()
        rows = self.db.fetchall("SELECT id, text FROM questions WHERE test_id = ? ORDER BY order_index", (test_id,))
        for i, row in enumerate(rows):
            text = row["text"]
            display = f"{i+1}. {text[:30]}..." if len(text) > 30 else f"{i+1}. {text}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setToolTip(text)
            self.questions_list.addItem(item)

    def _on_question_selected(self, current, _prev):
        if current is None:
            self._current_question_id = None
            self._clear_question_editor()
            return
        qid = current.data(Qt.ItemDataRole.UserRole)
        self._current_question_id = qid
        self._load_question(qid)

    def _load_question(self, qid):
        row = self.db.fetchone("SELECT * FROM questions WHERE id = ?", (qid,))
        if not row:
            return
        self.q_text.setPlainText(row["text"])
        idx = self.q_type.findData(row["qtype"])
        if idx >= 0:
            self.q_type.setCurrentIndex(idx)
        self.q_points.setValue(float(row["points"] or 1))
        self._clear_options()
        opts = self.db.fetchall("SELECT * FROM options WHERE question_id = ? ORDER BY id", (qid,))
        for o in opts:
            self._add_option_row(o["text"], bool(o["is_correct"]))

    def _clear_question_editor(self):
        self.q_text.clear()
        self.q_type.setCurrentIndex(0)
        self.q_points.setValue(1.0)
        self._clear_options()
        self._current_question_id = None

    def _clear_options(self):
        """Безпечне очищення рядків варіантів та радіогрупи."""
        # Видаляємо віджети
        while self.options_container.count():
            item = self.options_container.takeAt(0)
            if item and item.widget():
                try:
                    item.widget().deleteLater()
                except RuntimeError:
                    pass
        self._option_rows.clear()
        
        # Безпечно видаляємо радіогрупу
        if self._radio_group is not None:
            try:
                # Видаляємо всі кнопки з групи
                for btn in self._radio_group.buttons():
                    try:
                        self._radio_group.removeButton(btn)
                    except RuntimeError:
                        pass
                self._radio_group.deleteLater()
            except RuntimeError:
                pass
            self._radio_group = None

    def _add_option_row(self, text="", is_correct=False, focus=False):
        is_single = self._is_single_type()
        row = OptionRow(text, is_correct, is_single=is_single)
        row.remove_btn.clicked.connect(lambda checked=False, r=row: self._remove_option_row(r))
        
        if is_single:
            if self._radio_group is None:
                self._radio_group = QButtonGroup(self)
                self._radio_group.setExclusive(True)
            try:
                self._radio_group.addButton(row.correct_widget)
            except RuntimeError:
                logger.warning("Не вдалося додати радіокнопку до групи")
        
        self.options_container.addWidget(row)
        self._option_rows.append(row)
        if focus:
            row.text_edit.setFocus()

    def _remove_option_row(self, row):
        """Безпечне видалення рядка варіанту."""
        try:
            if self._radio_group is not None and hasattr(row, 'correct_widget'):
                try:
                    self._radio_group.removeButton(row.correct_widget)
                except RuntimeError:
                    pass
            self.options_container.removeWidget(row)
            row.deleteLater()
            if row in self._option_rows:
                self._option_rows.remove(row)
        except RuntimeError:
            logger.warning("Помилка при видаленні рядка варіанту")

    def _expand_question(self):
        """Відкрити діалог для редагування повного тексту питання."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Редагування питання")
        dlg.setMinimumSize(500, 300)
        lay = QVBoxLayout(dlg)
        edit = QTextEdit()
        edit.setPlainText(self.q_text.toPlainText())
        lay.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec():
            self.q_text.setPlainText(edit.toPlainText())

    def _on_type_changed(self):
        try:
            qtype = self.q_type.currentData()
            self.options_group.setVisible(qtype != QuestionType.OPEN.value)
            self.open_group.setVisible(qtype == QuestionType.OPEN.value)
            self._rebuild_options()
        except RuntimeError:
            logger.warning("Помилка при зміні типу питання")

    def _rebuild_options(self):
        """Перестворює рядки варіантів з правильним типом кнопки."""
        try:
            data = [(r.get_data()[0], r.is_checked()) for r in self._option_rows]
            self._clear_options()
            for text, checked in data:
                self._add_option_row(text, checked)
        except RuntimeError:
            logger.warning("Помилка при перестворенні варіантів")

    def _add_question(self):
        if not self._current_test_id:
            return
        self.db.insert("questions", {
            "test_id": self._current_test_id,
            "text": "Нове питання",
            "qtype": QuestionType.SINGLE.value,
            "points": 1.0,
            "order_index": self.questions_list.count(),
        })
        self._load_questions(self._current_test_id)
        self.questions_list.setCurrentRow(self.questions_list.count() - 1)

    def _delete_question(self):
        if not self._current_question_id:
            return
        if Msg.question(self, "Видалити", "Видалити питання?") != Msg.StandardButton.Yes:
            return
        self.db.execute("DELETE FROM questions WHERE id = ?", (self._current_question_id,))
        self._load_questions(self._current_test_id)
        self._clear_question_editor()

    def _move_question(self, direction):
        if not self._current_question_id or not self._current_test_id:
            return
        current_row = self.questions_list.currentRow()
        new_row = current_row + direction
        if new_row < 0 or new_row >= self.questions_list.count():
            return
        current_id = self._current_question_id
        swap_item = self.questions_list.item(new_row)
        swap_id = swap_item.data(Qt.ItemDataRole.UserRole) if swap_item else None
        if not swap_id:
            return
        self.db.execute("UPDATE questions SET order_index = ? WHERE id = ?", (new_row, current_id))
        self.db.execute("UPDATE questions SET order_index = ? WHERE id = ?", (current_row, swap_id))
        self._load_questions(self._current_test_id)
        self.questions_list.setCurrentRow(new_row)

    def _save_question(self):
        if not self._current_question_id:
            return
        self.db.update("questions", {
            "text": self.q_text.toPlainText().strip(),
            "qtype": self.q_type.currentData(),
            "points": self.q_points.value(),
        }, "id = ?", (self._current_question_id,))
        self.db.execute("DELETE FROM options WHERE question_id = ?", (self._current_question_id,))
        for row in self._option_rows:
            text, correct = row.get_data()
            if text:
                self.db.insert("options", {"question_id": self._current_question_id, "text": text, "is_correct": int(correct)})
        self._load_questions(self._current_test_id)
        Msg.information(self, "Збережено", "Питання збережено.")

    def _import_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Імпорт", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            result = parse_excel(path)
            if result.errors:
                Msg.warning(self, "Імпорт", "\n".join(result.errors[:5]))
                return
            if not result.questions:
                Msg.information(self, "Імпорт", "Не знайдено питань.")
                return
            title, ok = Msg.getText(self, "Імпорт", "Назва тесту:", text="Імпортований тест")
            if not ok or not title.strip():
                return
            tid = self.db.insert("tests", {"title": title.strip(), "time_limit_minutes": 60, "created_at": _utc_now()})
            for i, q in enumerate(result.questions):
                payload = questions_to_db_payload([q], tid)
                if payload:
                    qid = self.db.insert("questions", payload[0]["question"])
                    for opt in payload[0].get("options", []):
                        opt["question_id"] = qid
                        self.db.insert("options", opt)
            self._load_tests()
            Msg.information(self, "Імпорт", f"Імпортовано {len(result.questions)} питань.")
        except Exception as exc:
            Msg.critical(self, "Помилка", str(exc))

    def _download_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "Шаблон", "template.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            generate_template(path)
            Msg.information(self, "Шаблон", f"Збережено: {path}")
        except Exception as exc:
            Msg.critical(self, "Помилка", str(exc))
