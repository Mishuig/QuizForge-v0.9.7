"""Детальні тести формування звіту."""
import json
from pathlib import Path

import pytest

from core.db import Database
from core.report_builder import build_report
from core.scoring import score_attempt


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "t.db")


def _seed(db: Database):
    tid = db.insert("tests", {
        "title": "Тест 1",
        "time_limit_minutes": 30,
        "violation_threshold": 5,
        "created_at": "2026-01-01T00:00:00",
    })
    qid = db.insert("questions", {
        "test_id": tid,
        "order_index": 0,
        "qtype": "single",
        "text": "2+2?",
        "points": 1,
    })
    oid = db.insert("options", {
        "question_id": qid,
        "order_index": 0,
        "text": "4",
        "is_correct": 1,
    })
    sid = db.insert("students", {
        "full_name": "Іван Тест",
        "email": "ivan@test.com",
        "test_id": tid,
    })
    aid = db.insert("attempts", {
        "student_id": sid,
        "test_id": tid,
        "status": "completed",
        "score": 0,
        "max_score": 1,
        "percent": 0,
        "start_time": "2026-01-01T00:00:00",
        "end_time": "2026-01-01T00:10:00",
    })
    db.insert("answers", {
        "attempt_id": aid,
        "question_id": qid,
        "selected": json.dumps([oid]),
        "is_correct": 1,
        "points_awarded": 1,
    })
    db.insert("violations", {
        "attempt_id": aid,
        "student_id": sid,
        "vtype": "focus_lost",
        "occurred_at": "2026-01-01T00:05:00",
        "question_number": 1,
        "details": "тест",
    })
    return aid


def test_build_report_creates_pdf(db, tmp_path):
    aid = _seed(db)
    path = build_report(db, aid)
    assert path.is_file()
    assert path.suffix == ".pdf"
    assert path.stat().st_size > 500


def test_build_report_missing_attempt(db):
    with pytest.raises(ValueError):
        build_report(db, 99999)


def test_score_then_report(db):
    aid = _seed(db)
    score_attempt(db, aid, partial_credit=False)
    path = build_report(db, aid)
    assert path.is_file()
