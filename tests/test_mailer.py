"""Тести валідації мейлера (без реальної відправки)."""
import pytest

from core.mailer import MailerError, send_email


def test_no_host():
    with pytest.raises(MailerError, match="from_address"):
        send_email({"smtp": {}}, "a@b.com", "s", "b")


def test_no_recipients():
    with pytest.raises(MailerError, match="одержувач"):
        send_email({"smtp": {"host": "h", "from_address": "a@b.com"}}, [], "s", "b")


def test_no_from():
    with pytest.raises(MailerError, match="from_address"):
        send_email({"smtp": {"host": "h"}}, "a@b.com", "s", "b")
