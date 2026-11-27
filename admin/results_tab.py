"""
Вкладка «Результати»: таблиця спроб, деталі, PDF, повторна відправка, експорт Excel.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QGridLayout, QFrame,
)

from core.db import Database
from core.dialogs import Msg, ThemedDialog
from core.ui_kit import icon_button, button_row, AdaptiveLabel
from core.ui_theme import colored_item, status_item
from core.report_builder import build_report, send_report

logger = logging.getLogger(__name__)

STATUS_UA = {"waiting": "Очікує", "in_progress": "Проходить", "completed": "Завершено", "blocked": "Заблоковано", "aborted": "Завершено користувачем"}


def _fmt_dt(iso):
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(iso)[:16]


def _fmt_duration(start, end, qtimes_sum=0):
    sec = qtimes_sum
    if start and end:
        try:
            t0 = datetime.fromisoformat(start)
            t1 = datetime.fromisoformat(end)
            sec = max(sec, int((t1 - t0).total_seconds()))
        except Exception:
            pass
    sec = max(0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class DetailsDialog(ThemedDialog):
    def __init__(self, db, attempt_id, parent=None):
        attempt = db.fetchone("SELECT * FROM attempts WHERE id = ?", (attempt_id,))
        student = db.fetchone("SELECT * FROM students WHERE id = ?", (attempt["student_id"],)) if attempt else None
        test = db.fetchone("SELECT * FROM tests WHERE id = ?", (attempt["test_id"],)) if attempt else None

        def _g(row, key, default=""):
            if row is None:
                return default
            try:
                return row[key] if row[key] is not None else default
            except (KeyError, IndexError):
                return default

        super().__init__(parent, f"Спроба #{attempt_id}", f"{_g(student, 'email')} · {_g(test, 'title')}", min_width=720, scroll=True)
        self.db = db
        self.attempt_id = attempt_id
        self.setMinimumHeight(460)
        self.resize(980, 720)

        pct = float(_g(attempt, "percent", 0) or 0)
        kind = "ok" if pct >= 70 else "warn" if pct >= 50 else "bad"
        vcount = db.fetchone("SELECT COUNT(*) AS c FROM violations WHERE attempt_id = ?", (attempt_id,))
        vc = int(vcount["c"]) if vcount else 0

        stats = QGridLayout()
        cards = [("Бали", f"{_g(attempt, 'score', 0):g}/{_g(attempt, 'max_score', 0):g}", kind),
                 ("Результат", f"{pct:g}%", kind), ("Порушення", str(vc), "ok" if vc == 0 else "bad"),
                 ("Статус", STATUS_UA.get(_g(attempt, "status"), ""), "")]
        for col, (cap, val, tone) in enumerate(cards):
            card = QFrame()
            card.setObjectName("statCard")
            lay = QVBoxLayout(card)
            c = QLabel(cap)
            c.setObjectName("fieldLabel")
            v = QLabel(val)
            v.setObjectName("statValue")
            lay.addWidget(c)
            lay.addWidget(v)
            stats.addWidget(card, 0, col)
        self.body.addLayout(stats)

        self.body.addWidget(QLabel("Відповіді"))
        ans_table = QTableWidget(0, 4)
        ans_table.setHorizontalHeaderLabels(["№", "Питання", "Відповідь", "Бали"])
        ans_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ans_table.verticalHeader().setVisible(False)
        self.body.addWidget(ans_table)

        self.add_button("Закрити", accept=True, primary=True)


class ResultsTab(QWidget):
    def __init__(self, db, config, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config
        self._build_ui()
        self.reload()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = AdaptiveLabel("Результати", max_font=22, min_font=14)
        title.setObjectName("titleLabel")
        root.addWidget(title)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Користувач", "Email", "Тест", "Бали", "%", "Час", "Порушення", "Статус", "ID"])
        self.table.setColumnHidden(8, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._show_details)
        root.addWidget(self.table, stretch=1)

        self.btn_details = icon_button("fa5s.eye", "Деталі", "#3b82f6", accent=True)
        self.btn_details.clicked.connect(self._show_details)
        self.btn_pdf = icon_button("fa5s.file-pdf", "Відкрити PDF")
        self.btn_pdf.clicked.connect(self._open_pdf)
        self.btn_resend = icon_button("fa5s.paper-plane", "Надіслати повторно")
        self.btn_resend.clicked.connect(self._resend)
        self.btn_export = icon_button("fa5s.file-export", "Експорт Excel")
        self.btn_export.clicked.connect(self._export_excel)
        self.btn_refresh = icon_button("fa5s.sync", "Оновити")
        self.btn_refresh.clicked.connect(self.reload)

        root.addWidget(button_row(self.btn_details, self.btn_pdf, self.btn_resend, self.btn_export, self.btn_refresh))

        self.stats = QLabel("")
        self.stats.setObjectName("subtitleLabel")
        root.addWidget(self.stats)

    def reload(self):
        rows = self.db.fetchall("""
            SELECT a.id, a.score, a.max_score, a.percent, a.status, a.report_sent, a.report_path,
                   s.full_name, s.email, t.title AS test_title,
                   (SELECT COUNT(*) FROM violations v WHERE v.attempt_id = a.id) AS vcount
            FROM attempts a JOIN students s ON s.id = a.student_id JOIN tests t ON t.id = a.test_id
            WHERE a.status IN ('completed', 'blocked', 'aborted', 'in_progress') ORDER BY a.id DESC
        """)
        self._rows = [dict(r) for r in rows]
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(r.get("full_name") or ""))
            self.table.setItem(i, 1, QTableWidgetItem(r.get("email") or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r.get("test_title") or ""))
            pct = float(r.get("percent") or 0)
            pkind = "ok" if pct >= 70 else "warn" if pct >= 50 else "bad"
            self.table.setItem(i, 3, colored_item(f"{r.get('score') or 0:g}/{r.get('max_score') or 0:g}", pkind))
            self.table.setItem(i, 4, colored_item(f"{pct:g}%", pkind))
            self.table.setItem(i, 5, QTableWidgetItem("—"))
            vc = int(r.get("vcount") or 0)
            self.table.setItem(i, 6, colored_item(str(vc), "muted" if vc == 0 else "bad"))
            st = STATUS_UA.get(r.get("status") or "", "")
            self.table.setItem(i, 7, status_item(st, "ok" if r.get("status") == "completed" else "bad"))
            id_item = QTableWidgetItem(str(r["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.table.setItem(i, 8, id_item)
        self.stats.setText(f"Усього спроб: {len(self._rows)}")

    def _selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 8)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _show_details(self):
        aid = self._selected_id()
        if aid is None:
            Msg.information(self, "Результати", "Виберіть рядок.")
            return
        DetailsDialog(self.db, aid, self).exec()

    def _open_pdf(self):
        aid = self._selected_id()
        if aid is None:
            Msg.information(self, "Результати", "Виберіть рядок.")
            return
        try:
            path = build_report(self.db, aid)
            import os, sys
            if sys.platform == "win32":
                os.startfile(str(path))
        except Exception as exc:
            Msg.critical(self, "PDF", str(exc))

    def _resend(self):
        aid = self._selected_id()
        if aid is None:
            Msg.information(self, "Результати", "Виберіть рядок.")
            return
        try:
            path = build_report(self.db, aid)
            send_report(self.db, self.config, aid, path)
            Msg.information(self, "Звіт", "Надіслано.")
            self.reload()
        except Exception as exc:
            Msg.critical(self, "Помилка", str(exc))

    def _export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Експорт", "results.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["Користувач", "Email", "Тест", "Бали", "%", "Статус"])
            for r in self._rows:
                ws.append([r.get("full_name"), r.get("email"), r.get("test_title"), r.get("score"), r.get("percent"), r.get("status")])
            wb.save(path)
            Msg.information(self, "Експорт", f"Збережено: {path}")
        except Exception as exc:
            Msg.critical(self, "Помилка", str(exc))
