"""
Тести імпорту користувачів з CSV/Excel.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class MockDB:
    """Мок бази даних для тестів."""
    def __init__(self):
        self.students = []
        self._next_id = 1

    def fetchone(self, query, params=()):
        if "email" in query.lower():
            email = params[0] if params else ""
            for s in self.students:
                if s["email"] == email:
                    return s
        return None

    def insert(self, table, data):
        data["id"] = self._next_id
        self._next_id += 1
        self.students.append(data)
        return data["id"]


def parse_csv_logic(path: Path) -> list[dict]:
    """Логіка парсингу CSV (без GUI)."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def import_students_logic(rows: list[dict], db: MockDB) -> tuple[int, int]:
    """Логіка імпорту (без GUI)."""
    imported = 0
    skipped = 0
    for r in rows:
        email = _normalize_email(r.get("email", ""))
        name = (r.get("name") or r.get("full_name") or "").strip()
        if not email or "@" not in email or not name:
            skipped += 1
            continue
        existing = db.fetchone("SELECT id FROM students WHERE email = ?", (email,))
        if existing:
            skipped += 1
            continue
        db.insert("students", {"full_name": name, "email": email, "attempts_allowed": 1})
        imported += 1
    return imported, skipped


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def tmp_csv(tmp_path: Path):
    return tmp_path / "students.csv"


def test_parse_csv_valid(tmp_csv: Path):
    with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email"])
        writer.writeheader()
        writer.writerow({"name": "Іванов Іван", "email": "ivan@test.com"})
        writer.writerow({"name": "Петренко Петро", "email": "petro@test.com"})
    rows = parse_csv_logic(tmp_csv)
    assert len(rows) == 2
    assert rows[0]["name"] == "Іванов Іван"
    assert rows[1]["email"] == "petro@test.com"


def test_import_valid_students(mock_db, tmp_csv: Path):
    with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email"])
        writer.writeheader()
        writer.writerow({"name": "Іванов Іван", "email": "ivan@test.com"})
        writer.writerow({"name": "Петренко Петро", "email": "petro@test.com"})
    rows = parse_csv_logic(tmp_csv)
    imported, skipped = import_students_logic(rows, mock_db)
    assert imported == 2
    assert skipped == 0
    assert len(mock_db.students) == 2


def test_import_skip_duplicates(mock_db, tmp_csv: Path):
    mock_db.insert("students", {"full_name": "Існуючий", "email": "ivan@test.com", "attempts_allowed": 1})
    with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email"])
        writer.writeheader()
        writer.writerow({"name": "Іванов Іван", "email": "ivan@test.com"})
        writer.writerow({"name": "Новий", "email": "new@test.com"})
    rows = parse_csv_logic(tmp_csv)
    imported, skipped = import_students_logic(rows, mock_db)
    assert imported == 1
    assert skipped == 1


def test_import_skip_invalid(mock_db, tmp_csv: Path):
    with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email"])
        writer.writeheader()
        writer.writerow({"name": "", "email": "ivan@test.com"})
        writer.writerow({"name": "Без email", "email": ""})
        writer.writerow({"name": "Невірний", "email": "not-an-email"})
        writer.writerow({"name": "Валідний", "email": "valid@test.com"})
    rows = parse_csv_logic(tmp_csv)
    imported, skipped = import_students_logic(rows, mock_db)
    assert imported == 1
    assert skipped == 3


def test_normalize_email():
    assert _normalize_email("  Test@Example.COM  ") == "test@example.com"
    assert _normalize_email("") == ""
    assert _normalize_email(None) == ""


def test_import_with_full_name_column(mock_db, tmp_csv: Path):
    with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["full_name", "email"])
        writer.writeheader()
        writer.writerow({"full_name": "Сидоренко Сидір", "email": "sidor@test.com"})
    rows = parse_csv_logic(tmp_csv)
    imported, skipped = import_students_logic(rows, mock_db)
    assert imported == 1
    assert mock_db.students[0]["full_name"] == "Сидоренко Сидір"
