"""
SecureTest Admin — головне вікно з вкладками.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFontDatabase, QFont, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QPushButton, QStackedWidget, QApplication, QDialog,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QVBoxLayout, QWidget, QSizePolicy,
)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config_loader import load_config
from core.dialogs import Msg, ThemedDialog
from core import ui_theme
from core.ui_kit import ThemedLogo, ThemeToggle, field
from core.ui_theme import ASSETS, apply_theme, logo_pixmap
from core.db import get_db
from core.admin_auth import is_password_set, set_password, verify_password
from admin.tests_tab import TestsTab
from admin.students_tab import StudentsTab
from admin.results_tab import ResultsTab

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("admin")


class PasswordDialog(ThemedDialog):
    def __init__(self, mode: str = "login", parent=None):
        setup = mode == "setup"
        super().__init__(parent, "Перший запуск" if setup else "Вхід адміністратора",
            "Встановіть пароль." if setup else "Введіть пароль.",
            min_width=360, max_width=480, icon_pixmap=logo_pixmap("logo-admin.png", 64), centered=True)
        self.mode = mode
        self.setWindowTitle("QuizForge — Адмін")
        self.setWindowIcon(QIcon(str(ASSETS / "logo-admin.png")))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("Пароль")
        self.pass_edit.returnPressed.connect(self._validate)
        self._pw_visible = False
        eye = self.pass_edit.addAction(self.style().standardIcon(self.style().StandardPixmap.SP_TitleBarNormalButton), QLineEdit.ActionPosition.TrailingPosition)
        eye.triggered.connect(self._toggle_pw)
        self.body.addWidget(field("Пароль", self.pass_edit))
        self.pass2_edit = None
        if setup:
            self.pass2_edit = QLineEdit()
            self.pass2_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.pass2_edit.setPlaceholderText("Повторіть")
            self.body.addWidget(field("Підтвердження", self.pass2_edit))
        self.error = self.make_error_label()
        self.body.addWidget(self.error)
        self.add_button("Скасувати")
        self.add_button("Зберегти" if setup else "Увійти", primary=True, default=True, callback=self._validate)
        self.pass_edit.setFocus()

    def _toggle_pw(self):
        self._pw_visible = not self._pw_visible
        mode = QLineEdit.EchoMode.Normal if self._pw_visible else QLineEdit.EchoMode.Password
        self.pass_edit.setEchoMode(mode)
        if self.pass2_edit:
            self.pass2_edit.setEchoMode(mode)

    def _fail(self, text):
        self.error.setText(text)
        self.error.show()

    def _validate(self):
        p1 = self.pass_edit.text()
        if self.mode == "setup":
            p2 = self.pass2_edit.text() if self.pass2_edit else ""
            if len(p1) < 4:
                self._fail("Мінімум 4 символи.")
                return
            if p1 != p2:
                self._fail("Паролі не збігаються.")
                return
        elif not p1:
            self._fail("Введіть пароль.")
            return
        self.accept()

    def password(self):
        return self.pass_edit.text()


class MainWindow(QMainWindow):
    def __init__(self, db, config, org_name="SecureTest"):
        super().__init__()
        self.db = db
        self.config = config
        self.setWindowTitle("QuizForge — Адміністрування")
        self.setWindowIcon(QIcon(str(ASSETS / "logo-admin.png")))
        self.setMinimumSize(380, 380)
        self.resize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("topbar")
        topbar.setMinimumHeight(72)
        topbar.setMaximumHeight(80)
        self._topbar_layout = QHBoxLayout(topbar)
        self._topbar_layout.setContentsMargins(16, 8, 16, 8)
        self._topbar_layout.setSpacing(12)

        self._topbar_layout.addWidget(ThemedLogo("logo-admin.png", 60))
        title = QLabel("QuizForge")
        title.setObjectName("logoLabel")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        self._topbar_layout.addWidget(title)
        self._topbar_layout.addSpacing(24)

        self.btn_tests = QPushButton("Тести")
        self.btn_users = QPushButton("Користувачі")
        self.btn_results = QPushButton("Результати")
        for b in (self.btn_tests, self.btn_users, self.btn_results):
            b.setObjectName("navTab")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            self._topbar_layout.addWidget(b)
        self._topbar_layout.addStretch(1)
        self._topbar_layout.addWidget(ThemeToggle())
        root.addWidget(topbar)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tests_tab = TestsTab(db)
        self.students_tab = StudentsTab(db, config)
        self.results_tab = ResultsTab(db, config)
        self.stack.addWidget(self.tests_tab)
        self.stack.addWidget(self.students_tab)
        self.stack.addWidget(self.results_tab)
        root.addWidget(self.stack, 1)

        self.btn_tests.clicked.connect(lambda: self._switch(0))
        self.btn_users.clicked.connect(lambda: self._switch(1))
        self.btn_results.clicked.connect(lambda: self._switch(2))
        self._switch(0)

    def _switch(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_tests.setChecked(index == 0)
        self.btn_users.setChecked(index == 1)
        self.btn_results.setChecked(index == 2)
        if index == 1:
            self.students_tab.reload()
        elif index == 2:
            self.results_tab.reload()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.width()
        
        if width < 600:
            font_size = 12
            margin = 8
            spacing = 4
        elif width < 900:
            font_size = 13
            margin = 12
            spacing = 6
        else:
            font_size = 14
            margin = 16
            spacing = 8
        
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)
        
        self._topbar_layout.setContentsMargins(margin, 8, margin, 8)
        self._topbar_layout.setSpacing(spacing)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SecureTest Admin")
    app.setWindowIcon(QIcon(str(ASSETS / "logo-admin.png")))
    try:
        config = load_config()
    except Exception as exc:
        Msg.critical(None, "Помилка", f"Не вдалося завантажити config.json:\n{exc}")
        return 1
    org = config.get("organization", {})
    apply_theme(app, org.get("accent_color", "#3b82f6"), org.get("theme", "light"))
    if not is_password_set(config):
        dlg = PasswordDialog(mode="setup")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return 0
        config = set_password(dlg.password(), config)
    else:
        dlg = PasswordDialog(mode="login")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return 0
        if not verify_password(dlg.password(), config):
            Msg.critical(None, "Доступ", "Невірний пароль.")
            return 1
    db = get_db()
    window = MainWindow(db, config, org.get("name", "SecureTest"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
