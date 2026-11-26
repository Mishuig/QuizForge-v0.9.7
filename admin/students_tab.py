"""
Вкладка «Користувачі» — білий список, імпорт, спроби, повторна спроба.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QGridLayout,
)

from core.db import Database
from core.ui_kit import field, icon_button
from core.dialogs import Msg, Input, ThemedDialog
from core.ui_theme import status_item
from core.mailer import MailerError, send_test_message

logger = logging.getLogger(__name__)

STATUS_KIND = {"waiting": "muted", "in_progress": "info", "completed": "ok", "blocked": "bad"}
STATUS_LABELS = {"waiting": "Очікує", "in_progress": "Проходить", "completed": "Завершено", "blocked": "Заблоковано"}


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class StudentDialog(ThemedDialog):
    def __init__(self, db, parent=None, student_id=None, data=None):
        super().__init__(parent, "Редагувати" if student_id else "Новий користувач",
            "Користувач зможе пройти тест за кодом на пошту.", min_width=520, max_width=760)
        self.db = db
        self.student_id = student_id
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Прізвище Ім'я")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("name@company.com")
        self.test_combo = QComboBox()
        self.test_combo.addItem("— не призначено —", None)
        for row in self.db.fetchall("SELECT id, title FROM tests ORDER BY title"):
            self.test_combo.addItem(row["title"], row["id"])
        self.attempts_spin = QSpinBox()
        self.attempts_spin.setRange(1, 100)
        self.attempts_spin.setValue(1)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)
        grid.addWidget(field("ПІБ", self.name_edit), 0, 0, 1, 2)
        grid.addWidget(field("Пошта", self.email_edit), 1, 0, 1, 2)
        grid.addWidget(field("Тест", self.test_combo), 2, 0)
        grid.addWidget(field("Спроб", self.attempts_spin), 2, 1)
        self.body.addLayout(grid)
        self.error = self.make_error_label()
        self.body.addWidget(self.error)
        self.add_button("Скасувати")
        self.add_button("Зберегти", primary=True, default=True, callback=self._validate_and_accept)
        if data:
            self.name_edit.setText(data.get("full_name", ""))
            self.email_edit.setText(data.get("email", ""))
            self.attempts_spin.setValue(int(data.get("attempts_allowed") or 1))
            tid = data.get("test_id")
            idx = self.test_combo.findData(tid)
            if idx >= 0:
                self.test_combo.setCurrentIndex(idx)
        self.name_edit.setFocus()

    def _fail(self, text):
        self.error.setText(text)
        self.error.show()

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        email = _normalize_email(self.email_edit.text())
        if not name:
            self._fail("Вкажіть ПІБ.")
            return
        if not email or "@" not in email:
            self._fail("Вкажіть коректну пошту.")
            return
        existing = self.db.fetchone("SELECT id FROM students WHERE email = ?", (email,))
        if existing and existing["id"] != self.student_id:
            self._fail(f"Пошта «{email}» уже є.")
            return
        self.accept()

    def get_data(self):
        return {"full_name": self.name_edit.text().strip(), "email": _normalize_email(self.email_edit.text()),
                "test_id": self.test_combo.currentData(), "attempts_allowed": self.attempts_spin.value()}


class StudentsTab(QWidget):
    def __init__(self, db, config, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config
        self._build_ui()
        self.reload()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 20)
        root.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Користувачі")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        top = QHBoxLayout()
        top.addWidget(QLabel("Пошук:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("ПІБ або email…")
        self.search_edit.textChanged.connect(self._apply_filter)
        top.addWidget(self.search_edit, stretch=1)
        top.addWidget(QLabel("Статус:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Усі", "")
        for key, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, key)
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        top.addWidget(self.status_filter)
        root.addLayout(top)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ПІБ", "Email", "Тест", "Спроб", "Статус", "ID"])
        self.table.setColumnHidden(5, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._edit_student)
        root.addWidget(self.table, stretch=1)

        # Icon buttons
        btns = QHBoxLayout()
        btns.setSpacing(8)
        self.btn_add = icon_button("fa5s.user-plus", "Додати", "#3b82f6", accent=True)
        self.btn_add.clicked.connect(self._add_student)
        self.btn_edit = icon_button("fa5s.edit", "Редагувати")
        self.btn_edit.clicked.connect(self._edit_student)
        self.btn_delete = icon_button("fa5s.trash", "Видалити", "#F87171", danger=True)
        self.btn_delete.clicked.connect(self._delete_student)
        self.btn_retry = icon_button("fa5s.redo", "Повторна спроба")
        self.btn_retry.clicked.connect(self._allow_retry)
        self.btn_import = icon_button("fa5s.file-import", "Імпорт")
        self.btn_import.clicked.connect(self._import_file)
        self.btn_smtp_test = icon_button("fa5s.envelope", "Тест SMTP")
        self.btn_smtp_test.clicked.connect(self._smtp_test)

        for b in (self.btn_add, self.btn_edit, self.btn_delete, self.btn_retry, self.btn_import):
            btns.addWidget(b)
        btns.addStretch()
        btns.addWidget(self.btn_smtp_test)
        root.addLayout(btns)

        self.stats_label = QLabel("")
        self.stats_label.setObjectName("subtitleLabel")
        root.addWidget(self.stats_label)

    def reload(self):
        rows = self.db.fetchall("""
            SELECT s.id, s.full_name, s.email, s.test_id, s.attempts_allowed, t.title AS test_title,
                   (SELECT a.status FROM attempts a WHERE a.student_id = s.id ORDER BY a.id DESC LIMIT 1) AS last_status,
                   (SELECT COUNT(*) FROM attempts a WHERE a.student_id = s.id AND a.status IN ('in_progress', 'completed', 'blocked')) AS used_attempts
            FROM students s LEFT JOIN tests t ON t.id = s.test_id ORDER BY s.full_name
        """)
        self._all_rows = [dict(r) for r in rows]
        self._apply_filter()

    def _apply_filter(self):
        query = self.search_edit.text().strip().lower()
        status_key = self.status_filter.currentData() or ""
        filtered = []
        for r in self._all_rows:
            status = r.get("last_status") or "waiting"
            if status_key and status != status_key:
                continue
            if query and query not in f"{r.get('full_name', '')} {r.get('email', '')}".lower():
                continue
            filtered.append(r)
        self.table.setRowCount(len(filtered))
        for i, r in enumerate(filtered):
            status = r.get("last_status") or "waiting"
            self.table.setItem(i, 0, QTableWidgetItem(r.get("full_name") or ""))
            self.table.setItem(i, 1, QTableWidgetItem(r.get("email") or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r.get("test_title") or "—"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{r.get('used_attempts') or 0}/{r.get('attempts_allowed') or 1}"))
            self.table.setItem(i, 4, status_item(STATUS_LABELS.get(status, status), STATUS_KIND.get(status, "muted")))
            id_item = QTableWidgetItem(str(r["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.table.setItem(i, 5, id_item)
        self.stats_label.setText(f"Показано: {len(filtered)} з {len(self._all_rows)}")

    def _selected_student_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 5)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_row_data(self):
        sid = self._selected_student_id()
        if sid is None:
            return None
        for r in self._all_rows:
            if r["id"] == sid:
                return r
        return None

    def _add_student(self):
        dlg = StudentDialog(self.db, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            sid = self.db.insert("students", data)
            self.db.log_audit("student_created", "admin", f"id={sid}")
            self.reload()
        except Exception as exc:
            Msg.critical(self, "Помилка", str(exc))

    def _edit_student(self):
        row = self._selected_row_data()
        if not row:
            Msg.information(self, "Користувачі", "Виберіть користувача.")
            return
        dlg = StudentDialog(self.db, self, student_id=row["id"], data=row)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            self.db.update("students", data, "id = ?", (row["id"],))
            self.reload()
        except Exception as exc:
            Msg.critical(self, "Помилка", str(exc))

    def _delete_student(self):
        row = self._selected_row_data()
        if not row:
            Msg.information(self, "Користувачі", "Виберіть користувача.")
            return
        if Msg.question(self, "Підтвердження", f"Видалити «{row['full_name']}»?") != Msg.StandardButton.Yes:
            return
        self.db.execute("DELETE FROM students WHERE id = ?", (row["id"],))
        self.reload()

    def _allow_retry(self):
        row = self._selected_row_data()
        if not row:
            Msg.information(self, "Користувачі", "Виберіть користувача.")
            return
        new_allowed = int(row.get("attempts_allowed") or 1) + 1
        self.db.update("students", {"attempts_allowed": new_allowed}, "id = ?", (row["id"],))
        Msg.information(self, "Повторна спроба", f"Дозволено спроб: {new_allowed}")
        self.reload()

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Імпорт", "", "Excel/CSV (*.xlsx *.csv)")
        if not path:
            return
        Msg.information(self, "Імпорт", f"Файл: {path}")

    def _smtp_test(self):
        try:
            send_test_message(self.config)
            Msg.information(self, "SMTP", "Тестове повідомлення надіслано.")
        except Exception as exc:
            Msg.critical(self, "SMTP", str(exc))

    def _parse_csv(self, path):
        return []

    def _parse_xlsx(self, path):
        return []
