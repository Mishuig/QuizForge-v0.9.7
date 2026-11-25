"""
Вкладка «Результати»: таблиця спроб, деталі, PDF, повторна відправка, експорт Excel.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from core.ui_kit import AdaptiveButton
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QGridLayout,
    QFrame,
)

from core.db import Database
from core.dialogs import Msg, ThemedDialog
from core.ui_theme import colored_item, status_item
from core.report_builder import build_report, send_report

logger = logging.getLogger(__name__)

STATUS_UA = {
    "waiting": "Очікує",
    "in_progress": "Проходить",
    "completed": "Завершено",
    "blocked": "Заблоковано",
    "aborted": "Завершено користувачем",
}


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(iso)[:16]


def _fmt_duration(start: str | None, end: str | None, qtimes_sum: int = 0) -> str:
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
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class DetailsDialog(ThemedDialog):
    """Деталі спроби: підсумок, відповіді, порушення, скріншоти (усе у скролі, адаптивно)."""

    def __init__(self, db: Database, attempt_id: int, parent: QWidget | None = None) -> None:
        attempt = db.fetchone("SELECT * FROM attempts WHERE id = ?", (attempt_id,))
        student = db.fetchone(
            "SELECT * FROM students WHERE id = ?", (attempt["student_id"],)
        ) if attempt else None
        test = db.fetchone(
            "SELECT * FROM tests WHERE id = ?", (attempt["test_id"],)
        ) if attempt else None

        def _g(row, key, default=""):
            if row is None:
                return default
            try:
                return row[key] if row[key] is not None else default
            except (KeyError, IndexError):
                return default

        super().__init__(
            parent,
            f"Спроба #{attempt_id} — {_g(student, 'full_name') or 'користувач'}",
            f"{_g(student, 'email')} · {_g(test, 'title')}",
            min_width=720,
            scroll=True,
        )
        self.db = db
        self.attempt_id = attempt_id
        self.setMinimumHeight(460)
        self.resize(980, 720)
        self.setSizeGripEnabled(True)

        # ---- підсумок: 4 картки в сітці
        pct = float(_g(attempt, "percent", 0) or 0)
        kind = "ok" if pct >= 70 else "warn" if pct >= 50 else "bad"
        vcount = db.fetchone(
            "SELECT COUNT(*) AS c FROM violations WHERE attempt_id = ?", (attempt_id,)
        )
        vc = int(vcount["c"]) if vcount else 0
        status_txt = STATUS_UA.get(_g(attempt, "status"), _g(attempt, "status"))
        cards = [
            ("Бали", f"{_g(attempt, 'score', 0):g} / {_g(attempt, 'max_score', 0):g}", kind),
            ("Результат", f"{pct:g} %", kind),
            ("Порушення", str(vc), "ok" if vc == 0 else "warn" if vc < 3 else "bad"),
            ("Статус", status_txt, ""),
        ]
        stats = QGridLayout()
        stats.setSpacing(12)
        for col, (cap, val, tone) in enumerate(cards):
            card = QFrame()
            card.setObjectName("statCard")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(16, 12, 16, 12)
            lay.setSpacing(2)
            c = QLabel(cap)
            c.setObjectName("fieldLabel")
            v = QLabel(val)
            v.setObjectName("statValue")
            v.setProperty("kind", tone)
            v.setWordWrap(True)
            lay.addWidget(c)
            lay.addWidget(v)
            stats.addWidget(card, 0, col)
            stats.setColumnStretch(col, 1)
        self.body.addLayout(stats)

        # ---- відповіді та час
        self.body.addWidget(self._section("Відповіді та час"))
        ans_table = QTableWidget(0, 5)
        ans_table.setHorizontalHeaderLabels(["№", "Питання", "Відповідь", "Бали", "Час (с)"])
        hh = ans_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        ans_table.verticalHeader().setVisible(False)
        ans_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ans_table.setMinimumHeight(180)

        questions = db.fetchall(
            "SELECT * FROM questions WHERE test_id = ? ORDER BY order_index, id",
            (attempt["test_id"],),
        ) if attempt else []
        qtimes = {
            r["question_id"]: r["seconds"]
            for r in db.fetchall(
                "SELECT question_id, seconds FROM question_times WHERE attempt_id = ?",
                (attempt_id,),
            )
        }
        answers = {
            r["question_id"]: r
            for r in db.fetchall("SELECT * FROM answers WHERE attempt_id = ?", (attempt_id,))
        }

        ans_table.setRowCount(len(questions))
        for i, q in enumerate(questions):
            ans = answers.get(q["id"])
            selected = (ans["selected"] if ans else "") or ""
            display = selected
            if q["qtype"] in ("single", "multiple") and selected:
                try:
                    import json
                    ids = json.loads(selected)
                    opts = {
                        o["id"]: o["text"]
                        for o in db.fetchall(
                            "SELECT id, text FROM options WHERE question_id = ?", (q["id"],)
                        )
                    }
                    display = ", ".join(opts.get(k, str(k)) for k in ids)
                except Exception:
                    pass
            pts_val = float(ans["points_awarded"]) if ans else 0.0
            ans_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            ans_table.setItem(i, 1, QTableWidgetItem((q["text"] or "")[:120]))
            ans_table.setItem(i, 2, QTableWidgetItem(display[:160]))
            ans_table.setItem(i, 3, colored_item(f"{pts_val:g}", "ok" if pts_val > 0 else "bad"))
            ans_table.setItem(i, 4, QTableWidgetItem(str(qtimes.get(q["id"], 0))))
        ans_table.resizeRowsToContents()
        self.body.addWidget(ans_table, 1)

        # ---- порушення
        self.body.addWidget(self._section("Порушення"))
        violations = db.fetchall(
            "SELECT * FROM violations WHERE attempt_id = ? ORDER BY occurred_at",
            (attempt_id,),
        )
        if violations:
            v_table = QTableWidget(len(violations), 4)
            v_table.setHorizontalHeaderLabels(["Час", "Тип", "Питання", "Деталі"])
            vh = v_table.horizontalHeader()
            vh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            vh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            vh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            vh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            v_table.verticalHeader().setVisible(False)
            v_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            v_table.setMinimumHeight(60 + 38 * min(len(violations), 5))
            for i, v in enumerate(violations):
                v_table.setItem(i, 0, QTableWidgetItem(_fmt_dt(v["occurred_at"])))
                v_table.setItem(i, 1, colored_item(v["vtype"], "bad"))
                v_table.setItem(i, 2, QTableWidgetItem(str(v["question_number"] or "—")))
                v_table.setItem(i, 3, QTableWidgetItem(v["details"] or ""))
            self.body.addWidget(v_table)
        else:
            ok_lbl = QLabel("Порушень немає.")
            ok_lbl.setObjectName("subtitleLabel")
            self.body.addWidget(ok_lbl)

        # ---- скріншоти: адаптивна сітка мініатюр
        shots = db.fetchall(
            "SELECT * FROM screenshots WHERE attempt_id = ? ORDER BY captured_at",
            (attempt_id,),
        )
        if shots:
            self.body.addWidget(self._section(f"Скріншоти ({len(shots)})"))
            gallery = QGridLayout()
            gallery.setSpacing(12)
            col = row = 0
            for sh in shots[:24]:
                fp = sh["file_path"]
                if fp and Path(fp).is_file():
                    pix = QPixmap(fp)
                    if pix.isNull():
                        continue
                    lbl = QLabel()
                    lbl.setPixmap(
                        pix.scaled(
                            220, 124,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    lbl.setToolTip(f"{sh['captured_at']}\n{fp}")
                    lbl.setObjectName("thumb")
                    gallery.addWidget(lbl, row, col)
                    col += 1
                    if col >= 3:
                        col, row = 0, row + 1
            for c in range(3):
                gallery.setColumnStretch(c, 1)
            self.body.addLayout(gallery)

        self.add_button("Закрити", accept=True, primary=True, default=True)

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl


class ResultsTab(QWidget):
    def __init__(self, db: Database, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.config = config
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        title = QLabel("Результати")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        self.table = QTableWidget(0, 9)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(
            [
                "Користувач",
                "Email",
                "Тест",
                "Бали",
                "%",
                "Час",
                "Порушення",
                "Статус",
                "ID",
            ]
        )
        self.table.setColumnHidden(8, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._show_details)
        root.addWidget(self.table, stretch=1)

        btns = QHBoxLayout()
        btns.setSpacing(12)
        self.btn_details = QPushButton("Деталі")
        self.btn_details.setObjectName("primaryButton")
        self.btn_details.setMinimumHeight(36)
        self.btn_details.clicked.connect(self._show_details)

        self.btn_pdf = AdaptiveButton("Відкрити PDF", "PDF")
        self.btn_pdf.setObjectName("secondaryButton")
        self.btn_pdf.setMinimumHeight(36)
        self.btn_pdf.clicked.connect(self._open_pdf)

        self.btn_resend = QPushButton("Повторити")
        self.btn_resend.setObjectName("secondaryButton")
        self.btn_resend.setMinimumHeight(36)
        self.btn_resend.clicked.connect(self._resend)

        self.btn_export = AdaptiveButton("Експорт Excel", "Експорт")
        self.btn_export.setObjectName("secondaryButton")
        self.btn_export.setMinimumHeight(36)
        self.btn_export.clicked.connect(self._export_excel)

        self.btn_refresh = QPushButton("Оновити")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.setMinimumHeight(36)
        self.btn_refresh.clicked.connect(self.reload)

        btns.addWidget(self.btn_details)
        btns.addWidget(self.btn_pdf)
        btns.addWidget(self.btn_resend)
        btns.addWidget(self.btn_export)
        btns.addStretch()
        btns.addWidget(self.btn_refresh)
        root.addLayout(btns)

        self.stats = QLabel("")
        self.stats.setObjectName("subtitleLabel")
        root.addWidget(self.stats)

    def reload(self) -> None:
        rows = self.db.fetchall(
            """
            SELECT a.id, a.score, a.max_score, a.percent, a.status, a.report_sent,
                   a.report_path, a.start_time, a.end_time,
                   s.full_name, s.email,
                   t.title AS test_title,
                   (SELECT COUNT(*) FROM violations v WHERE v.attempt_id = a.id) AS vcount,
                   (SELECT COALESCE(SUM(seconds), 0) FROM question_times qt
                    WHERE qt.attempt_id = a.id) AS time_sum
            FROM attempts a
            JOIN students s ON s.id = a.student_id
            JOIN tests t ON t.id = a.test_id
            WHERE a.status IN ('completed', 'blocked', 'aborted', 'in_progress')
            ORDER BY a.id DESC
            """
        )
        self._rows = [dict(r) for r in rows]
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(r.get("full_name") or ""))
            self.table.setItem(i, 1, QTableWidgetItem(r.get("email") or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r.get("test_title") or ""))
            score_txt = f"{r.get('score') or 0:g}/{r.get('max_score') or 0:g}"
            pct = float(r.get("percent") or 0)
            pkind = "ok" if pct >= 70 else "warn" if pct >= 50 else "bad"
            self.table.setItem(i, 3, colored_item(score_txt, pkind))
            self.table.setItem(i, 4, colored_item(f"{pct:g} %", pkind))
            self.table.setItem(
                i,
                5,
                QTableWidgetItem(
                    _fmt_duration(r.get("start_time"), r.get("end_time"), int(r.get("time_sum") or 0))
                ),
            )
            vc = int(r.get("vcount") or 0)
            self.table.setItem(i, 6, colored_item(str(vc), "muted" if vc == 0 else "warn" if vc < 3 else "bad"))
            st = STATUS_UA.get(r.get("status") or "", r.get("status") or "")
            sent = "Надіслано" if r.get("report_sent") else "Не відправлено"
            skind = {"completed": "ok", "blocked": "bad", "in_progress": "info"}.get(r.get("status") or "", "muted")
            self.table.setItem(i, 7, status_item(f"{st} / {sent}", skind))
            id_item = QTableWidgetItem(str(r["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.table.setItem(i, 8, id_item)

        self.stats.setText(f"Усього спроб: {len(self._rows)}")

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 8)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _show_details(self) -> None:
        aid = self._selected_id()
        if aid is None:
            Msg.information(self, "Результати", "Виберіть рядок у таблиці.")
            return
        DetailsDialog(self.db, aid, self).exec()

    def _open_pdf(self) -> None:
        aid = self._selected_id()
        if aid is None:
            Msg.information(self, "Результати", "Виберіть рядок у таблиці.")
            return
        row = self.db.fetchone("SELECT report_path FROM attempts WHERE id = ?", (aid,))
        path = Path(row["report_path"]) if row and row["report_path"] else None
        if not path or not path.is_file():
            try:
                path = build_report(self.db, aid)
            except Exception as exc:
                Msg.critical(self, "PDF", f"Не вдалося створити звіт:\n{exc}")
                return
        # Відкрити системним переглядачем
        import os
        import subprocess
        import sys

        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as exc:
            Msg.information(self, "PDF", f"Файл: {path}\n\n{exc}")

    def _resend(self) -> None:
        aid = self._selected_id()
        if aid is None:
            Msg.information(self, "Результати", "Виберіть рядок у таблиці.")
            return
        try:
            row = self.db.fetchone("SELECT report_path FROM attempts WHERE id = ?", (aid,))
            path = Path(row["report_path"]) if row and row["report_path"] else None
            if not path or not path.is_file():
                path = build_report(self.db, aid)
            ok = send_report(self.db, self.config, aid, path)
            if ok:
                Msg.information(self, "Відправка", "Звіт надіслано.")
            else:
                Msg.warning(
                    self,
                    "Відправка",
                    "Не вдалося надіслати. Перевірте SMTP і report_recipients у config.json.",
                )
            self.reload()
        except Exception as exc:
            logger.exception("resend")
            Msg.critical(self, "Помилка", str(exc))

    def _export_excel(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Експорт результатів",
            "results.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font

            wb = Workbook()
            ws = wb.active
            ws.title = "Результати"
            headers = [
                "ID спроби",
                "ПІБ",
                "Email",
                "Тест",
                "Бали",
                "Максимум",
                "%",
                "Склав",
                "Статус",
                "Початок",
                "Кінець",
                "Час (сек)",
                "Порушень",
                "Звіт надіслано",
                "Шлях до PDF",
            ]
            ws.append(headers)
            for c in ws[1]:
                c.font = Font(bold=True)

            for r in self._rows:
                att = self.db.fetchone("SELECT * FROM attempts WHERE id = ?", (r["id"],))
                ws.append(
                    [
                        r["id"],
                        r.get("full_name"),
                        r.get("email"),
                        r.get("test_title"),
                        r.get("score"),
                        r.get("max_score"),
                        r.get("percent"),
                        "так" if att and att["passed"] else ("ні" if att and att["passed"] is not None else "—"),
                        STATUS_UA.get(r.get("status") or "", r.get("status")),
                        r.get("start_time"),
                        r.get("end_time"),
                        r.get("time_sum"),
                        r.get("vcount"),
                        "так" if r.get("report_sent") else "ні",
                        r.get("report_path"),
                    ]
                )
            wb.save(path)
            Msg.information(self, "Експорт", f"Збережено:\n{path}")
        except Exception as exc:
            logger.exception("export")
            Msg.critical(self, "Помилка", str(exc))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            narrow = self.width() < 700
            # Columns: 0=Ім'я, 1=Email, 2=Тест, 3=Бали, 4=%, 5=Час, 6=Порушення, 7=Статус
            if self.table.columnCount() > 6:
                self.table.setColumnHidden(5, narrow)  # Час
                self.table.setColumnHidden(6, narrow)  # Порушення
        except Exception:
            pass
