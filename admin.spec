# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('client/ui', 'client/ui'), ('fonts', 'fonts')]
binaries = []
hiddenimports = ['admin', 'admin.students_tab', 'admin.tests_tab', 'admin.results_tab', 'core', 'core.ui_kit', 'core.ui_theme', 'core.db', 'PyQt6.QtSvg']

tmp = collect_all('admin')
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]
tmp = collect_all('core')
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

a = Analysis(['admin/main.py'], pathex=['.'], binaries=binaries, datas=datas, hiddenimports=hiddenimports, excludes=['tkinter'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='QuizForge-Admin', console=False, icon='assets/logo-admin.ico')
