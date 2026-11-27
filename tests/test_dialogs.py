"""Тести діалогів — перевіряють наявність методів без GUI.

Ці тести НЕ потребують PyQt6 графіки — тільки перевіряють що методи існують.
"""

import pytest


def test_msg_has_gettext():
    """Msg.getText існує (аліас для Input.getText)."""
    from core.dialogs import Msg
    assert hasattr(Msg, "getText"), "Msg.getText не існує"
    assert callable(Msg.getText), "Msg.getText не є методом"


def test_msg_has_information():
    """Msg.information існує."""
    from core.dialogs import Msg
    assert hasattr(Msg, "information")
    assert callable(Msg.information)


def test_msg_has_warning():
    """Msg.warning існує."""
    from core.dialogs import Msg
    assert hasattr(Msg, "warning")
    assert callable(Msg.warning)


def test_msg_has_critical():
    """Msg.critical існує."""
    from core.dialogs import Msg
    assert hasattr(Msg, "critical")
    assert callable(Msg.critical)


def test_msg_has_question():
    """Msg.question існує."""
    from core.dialogs import Msg
    assert hasattr(Msg, "question")
    assert callable(Msg.question)


def test_msg_has_choice():
    """Msg.choice існує."""
    from core.dialogs import Msg
    assert hasattr(Msg, "choice")
    assert callable(Msg.choice)


def test_input_has_gettext():
    """Input.getText існує."""
    from core.dialogs import Input
    assert hasattr(Input, "getText")
    assert callable(Input.getText)


def test_themed_dialog_exists():
    """ThemedDialog існує."""
    from core.dialogs import ThemedDialog
    assert ThemedDialog is not None
