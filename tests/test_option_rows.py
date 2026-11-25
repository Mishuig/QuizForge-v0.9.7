"""Тести додавання варіантів відповіді в редакторі питань.

Пропускаються, якщо PyQt6/GUI недоступні (CI без графічних бібліотек).
"""

import pytest

# Перевіряємо доступність PyQt6
try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    PYQT_AVAILABLE = True
except Exception:
    PYQT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PYQT_AVAILABLE,
    reason="PyQt6 або графічні бібліотеки недоступні"
)


def test_option_row_creation():
    """OptionRow створюється з текстом і позначкою."""
    from admin.tests_tab import OptionRow
    
    row = OptionRow("Варіант А", is_correct=True)
    text, correct = row.get_data()
    assert text == "Варіант А"
    assert correct is True


def test_option_row_empty():
    """Порожній OptionRow."""
    from admin.tests_tab import OptionRow
    
    row = OptionRow()
    text, correct = row.get_data()
    assert text == ""
    assert correct is False


def test_add_multiple_options():
    """Можна додати кілька варіантів підряд."""
    from admin.tests_tab import OptionRow
    
    rows = []
    for i in range(5):
        row = OptionRow(f"Варіант {i+1}", is_correct=(i == 0))
        rows.append(row)
    
    assert len(rows) == 5
    assert rows[0].get_data()[1] is True
    assert rows[1].get_data()[1] is False


def test_option_row_expand_exists():
    """Кнопка розгортання існує."""
    from admin.tests_tab import OptionRow
    
    row = OptionRow("Довгий текст варіанту")
    assert hasattr(row, "expand_btn")
    assert row.expand_btn is not None
