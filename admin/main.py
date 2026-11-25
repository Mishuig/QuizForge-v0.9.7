"""
SecureTest Admin — головне вікно з вкладками.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QFont, QPixmap
from PyQt6.QtWidgets import (
    QPushButton, QStackedWidget, QApplication, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QVBoxLayout, QWidget,
)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config_loader import load_config
from core.dialogs import Msg, ThemedDialog
from core.ui_kit import ThemedLogo, ThemeToggle, field
from core.ui_theme import ASSETS, apply_theme, logo_pixmap
from core.db import get_db
from core.admin_auth import is_password_set, set_password, verify_password
from admin.tests_tab import TestsTab
from admin.students_tab import StudentsTab
from admin.results_tab import ResultsTab

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PasswordDialog(ThemedDialog):
    def __init__(self, mode: str = "login", parent=None):
        super().__init__("Вхід" if mode == "login" else "Налаштування", parent)
        self.mode = mode
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("Пароль")
        self._pw_visible = False
        eye = self.pass_edit.addAction(
            self.style().standardIcon(self.style().StandardPixmap.SP_TitleBarNormalButton),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        eye.triggered.connect(self._toggle_pw)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Пароль адміністратора:"))
        layout.addWidget(self.pass_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _toggle_pw(self):
        self._pw_visible = not self._pw_visible
        mode = QLineEdit.EchoMode.Normal if self._pw_visible else QLineEdit.EchoMode.Password
        self.pass_edit.setEchoMode(mode)

    def get_password(self):
        return self.pass_edit.text()


class MainWindow(QMainWindow):
    def __init__(self, db, config, org_name="QuizForge"):
        super().__init__()
        self.db = db
        self.config = config
        self.setWindowTitle(f"{org_name} — Адмін")
        self.setMinimumSize(380, 380)
        self.resize(1280, 800)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        nav = QHBoxLayout()
        self.btn_tests = QPushButton("Тести")
        self.btn_tests.setObjectName("navTab")
        self.btn_users = QPushButton("Користувачі")
        self.btn_users.setObjectName("navTab")
        self.btn_results = QPushButton("Результати")
        self.btn_results.setObjectName("navTab")
        nav.addWidget(self.btn_tests)
        nav.addWidget(self.btn_users)
        nav.addWidget(self.btn_results)
        nav.addStretch()
        nav.addWidget(ThemeToggle())
        layout.addLayout(nav)
        self.stack = QStackedWidget()
        self.tests_tab = TestsTab(self.db, self.config)
        self.students_tab = StudentsTab(self.db, self.config)
        self.results_tab = ResultsTab(self.db, self.config)
        self.stack.addWidget(self.tests_tab)
        self.stack.addWidget(self.students_tab)
        self.stack.addWidget(self.results_tab)
        layout.addWidget(self.stack)
        self.btn_tests.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_users.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_results.clicked.connect(lambda: self.stack.setCurrentIndex(2))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QuizForge Admin")
    config = load_config()
    org = config.get("organization", {})
    apply_theme(app, org.get("accent_color", "#3b82f6"), org.get("theme", "dark"))
    db = get_db()
    if not is_password_set(db):
        dlg = PasswordDialog("setup")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return 1
        set_password(db, dlg.get_password())
    else:
        dlg = PasswordDialog("login")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return 1
        if not verify_password(db, dlg.get_password()):
            Msg.critical(None, "Помилка", "Невірний пароль")
            return 1
    window = MainWindow(db, config, org.get("name", "QuizForge"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
