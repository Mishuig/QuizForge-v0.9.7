"""
Спільна тема QuizForge (адмін-панель і клієнт): темна та світла.

Один QSS-шаблон `client/ui/styles.qss` з токенами @TOKEN@. Палітра обирається за темою,
акцент береться з config.json -> organization.accent_color. Вибір теми зберігається
у ui_prefs.json поруч із програмою (портативно, без реєстру).
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QFontDatabase, QPixmap
from PyQt6.QtWidgets import QApplication, QTableWidgetItem, QWidget

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
QSS_PATH = ROOT / "client" / "ui" / "styles.qss"
DEFAULT_ACCENT = "#3b82f6"
THEMES = ("dark", "light")

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "BG": "#0B0F17", "INPUT": "#0F1520", "SURFACE": "#131A26", "BTN": "#1A2332", "BTN_HOVER": "#222E42",
        "BORDER": "#243044", "BORDER2": "#2F3D55", "BORDER3": "#3B4A63", "ROW_LINE": "#1C2636",
        "ROW_HOVER": "#1A2536", "SELECT": "#1B2D4D", "TEXT": "#E6EDF7", "STRONG": "#FFFFFF",
        "MUTED": "#9AA8BD", "DISABLED": "#6B7A93", "RING": "#5B6B85", "TEXT2": "#D5DEEC",
        "HINT_TEXT": "#DBEAFE", "INFO_BG": "#12305E", "INFO_FG": "#93C5FD", "WARN_BG": "#4A3A0C",
        "WARN_FG": "#FDE68A", "ERR_BG": "#4A1D22", "ERR_FG": "#FCA5A5", "ERR_HOVER": "#3A1D22",
        "ERR_BORDER": "#7F2A33", "ERR_ACCENT": "#F87171", "OK_BG": "#0F3D2E", "OK_FG": "#6EE7B7",
        "OK_DOT": "#34D399",
    },
    "light": {
        "BG": "#F4F6FA", "INPUT": "#FFFFFF", "SURFACE": "#FFFFFF", "BTN": "#FFFFFF", "BTN_HOVER": "#F1F5F9",
        "BORDER": "#E2E8F0", "BORDER2": "#CBD5E1", "BORDER3": "#94A3B8", "ROW_LINE": "#EEF2F7",
        "ROW_HOVER": "#F1F5F9", "SELECT": "#DBEAFE", "TEXT": "#0F172A", "STRONG": "#0B1220",
        "MUTED": "#64748B", "DISABLED": "#94A3B8", "RING": "#94A3B8", "TEXT2": "#334155",
        "HINT_TEXT": "#1E3A8A", "INFO_BG": "#DBEAFE", "INFO_FG": "#1D4ED8", "WARN_BG": "#FEF3C7",
        "WARN_FG": "#92400E", "ERR_BG": "#FEE2E2", "ERR_FG": "#B91C1C", "ERR_HOVER": "#FEE2E2",
        "ERR_BORDER": "#FCA5A5", "ERR_ACCENT": "#DC2626", "OK_BG": "#D1FAE5", "OK_FG": "#047857",
        "OK_DOT": "#059669",
    },
}

# Кольори тексту статусів у таблицях (контраст ≥ 4.5:1 на фоні відповідної теми)
STATUS_COLORS: dict[str, dict[str, str]] = {
    "dark": {"ok": "#6EE7B7", "info": "#93C5FD", "warn": "#FDE68A", "bad": "#FCA5A5", "muted": "#B4C0D4"},
    "light": {"ok": "#047857", "info": "#1D4ED8", "warn": "#B45309", "bad": "#B91C1C", "muted": "#475569"},
}


class _Bus(QObject):
    changed = pyqtSignal(str)   # нова тема: "dark" | "light"


bus = _Bus()
_state: dict = {"app": None, "accent": DEFAULT_ACCENT, "theme": "dark"}


# ------------------------------------------------------------------ налаштування
def _prefs_path() -> Path:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT
    return base / "ui_prefs.json"


def _load_pref() -> str | None:
    try:
        data = json.loads(_prefs_path().read_text(encoding="utf-8"))
        theme = data.get("theme")
        return theme if theme in THEMES else None
    except (OSError, ValueError):
        return None


def _save_pref(theme: str) -> None:
    try:
        _prefs_path().write_text(json.dumps({"theme": theme}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Не вдалося зберегти налаштування теми")


def current_theme() -> str:
    return _state["theme"]


# ------------------------------------------------------------------ кольори й іконки
def _shade(hex_color: str, factor: float) -> str:
    c = QColor(hex_color)
    if not c.isValid():
        c = QColor(DEFAULT_ACCENT)
    return c.lighter(int(factor * 100)).name() if factor >= 1 else c.darker(int(100 / max(factor, 0.01))).name()


def _load_fonts(app: QApplication) -> None:
    """Підключає Inter з папки fonts/, якщо файли там є; інакше — системний шрифт."""
    family = None
    for path in sorted((ROOT / "fonts").glob("Inter*.[ot]tf")):
        fid = QFontDatabase.addApplicationFont(str(path))
        if fid != -1 and not family:
            fams = QFontDatabase.applicationFontFamilies(fid)
            family = fams[0] if fams else None
    if family:
        app.setFont(QFont(family, 10))


def _write_icons(accent: str, theme: str) -> str:
    """Генерує SVG-іконки (радіо, чекбокс, стрілки) під тему та акцент."""
    pal = PALETTES[theme]
    acc = QColor(accent).name()
    ring, bg, chevron = pal["RING"], pal["INPUT"], pal["MUTED"]
    icons = {
        "radio-off": f'<circle cx="10" cy="10" r="8" fill="{bg}" stroke="{ring}" stroke-width="2"/>',
        "radio-off-hover": f'<circle cx="10" cy="10" r="8" fill="{bg}" stroke="{acc}" stroke-width="2"/>',
        "radio-on": f'<circle cx="10" cy="10" r="8" fill="{bg}" stroke="{acc}" stroke-width="2"/><circle cx="10" cy="10" r="4.5" fill="{acc}"/>',
        "check-off": f'<rect x="1" y="1" width="18" height="18" rx="5" fill="{bg}" stroke="{ring}" stroke-width="2"/>',
        "check-off-hover": f'<rect x="1" y="1" width="18" height="18" rx="5" fill="{bg}" stroke="{acc}" stroke-width="2"/>',
        "check-on": f'<rect x="1" y="1" width="18" height="18" rx="5" fill="{acc}" stroke="{acc}" stroke-width="2"/>'
                    '<path d="M5.5 10.5l3 3 6-6.5" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    }
    folder = Path(tempfile.gettempdir()) / f"quizforge-ui-{theme}-{acc.lstrip('#')}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for name, body in icons.items():
            (folder / f"{name}.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="20" height="20">{body}</svg>',
                encoding="utf-8",
            )
        for name, d in (("chevron-down", "M2 4l4 4 4-4"), ("chevron-up", "M2 8l4-4 4 4")):
            (folder / f"{name}.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12" width="12" height="12">'
                f'<path d="{d}" fill="none" stroke="{chevron}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
                encoding="utf-8",
            )
    except OSError:
        logger.exception("Не вдалося створити іконки теми")
    return folder.as_posix()


def _render_qss(accent: str, theme: str) -> str:
    qss = QSS_PATH.read_text(encoding="utf-8")
    soft = QColor(accent)
    tokens = {f"@{k}@": v for k, v in PALETTES[theme].items()}
    tokens.update({
        "@ACCENT@": accent,
        "@ACCENT_HOVER@": _shade(accent, 1.12),
        "@ACCENT_PRESSED@": _shade(accent, 0.85),
        "@ACCENT_SOFT@": f"rgba({soft.red()},{soft.green()},{soft.blue()},{0x2E if theme == 'dark' else 0x1F})",
        "@ICONS@": _write_icons(accent, theme),
    })
    # довші токени першими (ACCENT_HOVER перед ACCENT тощо)
    for key in sorted(tokens, key=len, reverse=True):
        qss = qss.replace(key, tokens[key])
    return qss


# ------------------------------------------------------------------ публічне API
def apply_theme(app: QApplication, accent: str | None = None, default_theme: str = "dark") -> None:
    """Застосовує тему: збережений вибір користувача → default_theme → dark."""
    accent = accent if accent and QColor(accent).isValid() else DEFAULT_ACCENT
    theme = _load_pref() or (default_theme if default_theme in THEMES else "dark")
    _state.update(app=app, accent=accent, theme=theme)
    _load_fonts(app)
    if not QSS_PATH.is_file():
        logger.warning("Файл стилів не знайдено: %s", QSS_PATH)
        return
    app.setStyleSheet(_render_qss(accent, theme))


def set_theme(theme: str, persist: bool = True) -> None:
    """Перемикає тему на льоту й сповіщає віджети (bus.changed).
    
    Зберігає фокус, щоб не втрачати введення під час тесту.
    """
    if theme not in THEMES or theme == _state["theme"]:
        return
    app = _state["app"]
    if app is None or not QSS_PATH.is_file():
        return
    
    # Зберегти фокус
    focused = app.focusWidget()
    
    _state["theme"] = theme
    app.setStyleSheet(_render_qss(_state["accent"], theme))
    
    # Відновити фокус
    if focused is not None:
        focused.setFocus()
    
    if persist:
        _save_pref(theme)
    bus.changed.emit(theme)


def toggle_theme() -> None:
    set_theme("light" if _state["theme"] == "dark" else "dark")


def logo_pixmap(name: str, size: int) -> QPixmap:
    """Логотип з assets/; у світлій темі бере варіант `*-light.*`, якщо він є."""
    path = ASSETS / name
    if _state["theme"] == "light":
        alt = ASSETS / f"{path.stem}-light{path.suffix}"
        if alt.is_file():
            path = alt
    pm = QPixmap(str(path))
    if pm.isNull():
        return pm
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def repolish(widget: QWidget) -> None:
    """Перезастосовує QSS після зміни динамічної властивості."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _status_color(kind: str) -> QColor:
    pal = STATUS_COLORS[_state["theme"]]
    return QColor(pal.get(kind, pal["muted"]))


def status_item(text: str, kind: str = "muted") -> QTableWidgetItem:
    """Комірка таблиці зі статусом: «● Текст» кольором статусу."""
    item = QTableWidgetItem(f"● {text}")
    item.setForeground(QBrush(_status_color(kind)))
    font = item.font()
    font.setWeight(QFont.Weight.DemiBold)
    item.setFont(font)
    return item


def colored_item(text: str, kind: str, bold: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(QBrush(_status_color(kind)))
    if bold:
        font = item.font()
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(font)
    return item
