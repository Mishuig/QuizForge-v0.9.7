"""Тести пароля адміна."""
import json
from pathlib import Path

from core.admin_auth import verify_password, is_password_set, set_password


def test_is_password_set():
    assert not is_password_set({})
    assert not is_password_set({"admin_password_hash": ""})
    assert is_password_set({"admin_password_hash": "abc:def"})


def test_set_and_verify(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"organization": {"name": "T"}}), encoding="utf-8")
    cfg = {"organization": {"name": "T"}}
    new = set_password("mypass", cfg)
    assert is_password_set(new)
    assert verify_password("mypass", new)
    assert not verify_password("wrong", new)
