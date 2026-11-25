# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ('assets', 'assets'),
    ('client/ui', 'client/ui'),
    ('fonts', 'fonts'),
]
binaries = []
hiddenimports = [
    # Admin modules
    'admin',
    'admin.students_tab',
    'admin.tests_tab',
    'admin.results_tab',
    'admin.main',
    # Core modules
    'core',
    'core.ui_kit',
    'core.ui_theme',
    'core.db',
    'core.dialogs',
    'core.config_loader',
    'core.admin_auth',
    'core.mailer',
    'core.otp',
    'core.scoring',
    'core.report_builder',
    'core.excel_import',
    'core.models',
    # Qt
    'PyQt6',
    'PyQt6.QtSvg',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    # Icons
    'qtawesome',
    'qtawesome.iconic_font',
]

# Collect all submodules
tmp = collect_all('admin')
datas += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]

tmp = collect_all('core')
datas += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]

tmp = collect_all('qtawesome')
datas += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]

a = Analysis(
    ['admin/main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='QuizForge-Admin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/logo-admin.ico',
)
