"""
SecureTest Admin — головне вікно з вкладками.
"""

from __future__ import annotations

import logging
import sys
import os
from pathlib import Path

# === DIAGNOSTICS ===
if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    print(f"FROZEN: True")
    print(f"MEIPASS: {base}")
    print(f"Contents: {os.listdir(base)[:20]}")
    admin_path = os.path.join(base, 'admin')
    core_path = os.path.join(base, 'core')
    print(f"Admin exists: {os.path.exists(admin_path)}")
    if os.path.exists(admin_path):
        print(f"Admin files: {os.listdir(admin_path)}")
    print(f"Core exists: {os.path.exists(core_path)}")
    if os.path.exists(core_path):
        print(f"Core files: {os.listdir(core_path)[:10]}")
    print(f"sys.path: {sys.path[:5]}")
    # Add paths
    for p in [base, admin_path, core_path]:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
# === END DIAGNOSTICS ===

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QFont, QPixmap
from PyQt6.QtWidgets import (
    QPushButton, QStackedWidget, QApplication, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QVBoxLayout, QWidget,
)

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("admin")

# ... rest of file continues as before
