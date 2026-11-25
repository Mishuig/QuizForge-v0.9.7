"""Тести завантаження конфігурації."""
import json
from pathlib import Path

import pytest

from core.config_loader import load_config, ConfigError

ROOT = Path(__file__).resolve().parent.parent


def test_load_project_example():
    p = ROOT / "config.json.example"
    if not p.is_file():
        p = ROOT / "config.json"
    cfg = load_config(p)
    assert "organization" in cfg
    assert "smtp" in cfg


def test_missing_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.json")


def test_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ broken", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)
