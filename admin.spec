# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Explicitly add source folders as data
datas = [
    ('assets', 'assets'),
    ('client/ui', 'client/ui'),
    ('fonts', 'fonts'),
    ('admin', 'admin'),
    ('core', 'core'),
]
binaries = []
hiddenimports = collect_submodules('admin') + collect_submodules('core') + [
    'admin',
    'admin.students_tab',
    'admin.tests_tab',
    'admin.results_tab',
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
    'PyQt6.QtSvg',
    'PyQt6.sip',
    'qtawesome',
]

a = Analysis(
    ['admin/main.py'],
    pathex=['.', 'admin', 'core'],
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
