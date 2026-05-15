"""
Tests for database init, CRUD operations, and query helpers.

Each test gets a fresh in-memory SQLite database via the `db` fixture so
tests are fully isolated and leave no files on disk.
"""
import pytest

import database


JOB_DEFAULTS = {
    "source": "adzuna",
    "title": "Software Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "description": "We build cool things.",
    "url": "https://example.com/job/1",
    "salary_min": None,
    "salary_max": None,
    "posted_date": "2026-01-01",
    "fetched_at": "2026-01-01T00:00:00+00:00",
    "score": 75,
    "summary": "Good match.",
    "match_reasons": ["Python", "Remote"],
    "analyzed_at": "2026-01-01T00:00:01+00:00",
}


def _make_job(job_id: str, **overrides) -> dict:
    return {"id": job_id, **JOB_DEFAULTS, **overrides}


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Redirect all DB operations to a temporary file, then reinitialise."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    return database


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_required_tables(self, db):
        with db.get_conn() as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert {"jobs", "scan_log", "settings"} <= tables

    def test_seeds_settings_for_all_sources(self, db):
        settings = db.get_all_settings()
        sources = {s["source"] for s in settings}
        assert sources == {"adzuna", "remotive", "remoteok", "themuse"}

    def test_init_db_is_idempotent(self, db):
        db.init_db()  # second call must not raise or duplicate data
        assert len(db.get_all_settings()) == 4


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class TestInsertAndGet:
    def test_empty_db_returns_no_jobs(self, db):
        assert db.get_jobs() == []

    def test_insert_and_retrieve(self, db):
        db.insert_job(_make_job("adzuna_1", title="Python Dev"))
        jobs = db.get_jobs()
        assert len(jobs) == 1
        assert jobs[0]["id"] == "adzuna_1"
        assert jobs[0]["title"] == "Python Dev"

    def test_match_reasons_round_trips_as_list(self, db):
        db.insert_job(_make_job("adzuna_1", match_reasons=["a", "b", "c"]))
        job = db.get_job_by_id("adzuna_1")
        assert job["match_reasons"] == ["a", "b", "c"]

    def test_insert_or_ignore_does_not_overwrite(self, db):
        db.insert_job(_make_job("adzuna_1", score=75))
        db.insert_job(_make_job("adzuna_1", score=99))  # duplicate — should be ignored
        assert db.get_job_by_id("adzuna_1")["score"] == 75

    def test_get_job_by_id_missing_returns_none(self, db):
        assert db.get_job_by_id("does_not_exist") is None

    def test_min_score_filter(self, db):
        for i, score in enumerate([30, 60, 90]):
            db.insert_job(_make_job(f"job_{i}", score=score))

        assert len(db.get_jobs(min_score=0)) == 3
        assert len(db.get_jobs(min_score=60)) == 2
        assert len(db.get_jobs(min_score=91)) == 0

    def test_jobs_sorted_by_score_descending(self, db):
        for i, score in enumerate([40, 90, 60]):
            db.insert_job(_make_job(f"job_{i}", score=score))

        scores = [j["score"] for j in db.get_jobs()]
        assert scores == sorted(scores, reverse=True)

    def test_get_existing_ids(self, db):
        db.insert_job(_make_job("adzuna_1"))
        db.insert_job(_make_job("remotive_2"))
        assert db.get_existing_ids() == {"adzuna_1", "remotive_2"}


class TestToggleDismissed:
    def test_dismisses_job(self, db):
        db.insert_job(_make_job("adzuna_1"))
        assert db.toggle_dismissed("adzuna_1") is True
        assert db.get_job_by_id("adzuna_1")["dismissed"] is True

    def test_undismisses_job(self, db):
        db.insert_job(_make_job("adzuna_1"))
        db.toggle_dismissed("adzuna_1")
        assert db.toggle_dismissed("adzuna_1") is False
        assert db.get_job_by_id("adzuna_1")["dismissed"] is False


class TestToggleApplied:
    def test_marks_applied(self, db):
        db.insert_job(_make_job("adzuna_1"))
        result = db.toggle_applied("adzuna_1")
        assert result["applied_at"] is not None
        assert db.get_job_by_id("adzuna_1")["applied_at"] is not None

    def test_unmarks_applied(self, db):
        db.insert_job(_make_job("adzuna_1"))
        db.toggle_applied("adzuna_1")
        result = db.toggle_applied("adzuna_1")
        assert result["applied_at"] is None


# ---------------------------------------------------------------------------
# Scan log
# ---------------------------------------------------------------------------

class TestScanLog:
    def test_get_last_scan_empty(self, db):
        assert db.get_last_scan() is None

    def test_log_and_retrieve_scan(self, db):
        db.log_scan("2026-01-01T06:00:00+00:00", 12, "success", "adzuna")
        last = db.get_last_scan()
        assert last["new_jobs_found"] == 12
        assert last["status"] == "success"
        assert last["source"] == "adzuna"

    def test_get_last_scan_returns_most_recent(self, db):
        db.log_scan("2026-01-01T06:00:00+00:00", 5, "success", "adzuna")
        db.log_scan("2026-01-02T06:00:00+00:00", 8, "success", "remotive")
        assert db.get_last_scan()["new_jobs_found"] == 8


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_save_and_retrieve_settings(self, db):
        db.save_settings([{
            "source": "adzuna",
            "enabled": True,
            "keywords": "python developer",
            "location": "New York",
            "count": 100,
        }])
        settings = {s["source"]: s for s in db.get_all_settings()}
        assert settings["adzuna"]["keywords"] == "python developer"
        assert settings["adzuna"]["location"] == "New York"
        assert settings["adzuna"]["count"] == 100
