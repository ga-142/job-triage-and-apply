import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).parent / "jobs.db")))

SOURCES = ["adzuna", "remotive", "remoteok", "themuse"]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                description TEXT,
                url TEXT,
                salary_min REAL,
                salary_max REAL,
                posted_date TEXT,
                fetched_at TEXT,
                score INTEGER,
                summary TEXT,
                match_reasons TEXT,
                analyzed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at TEXT,
                new_jobs_found INTEGER,
                status TEXT,
                source TEXT DEFAULT ''
            );
        """)

        # --- jobs column migrations ---
        if not _column_exists(conn, "jobs", "dismissed"):
            conn.execute("ALTER TABLE jobs ADD COLUMN dismissed INTEGER DEFAULT 0")
        if not _column_exists(conn, "jobs", "applied_at"):
            conn.execute("ALTER TABLE jobs ADD COLUMN applied_at TEXT")
        if not _column_exists(conn, "jobs", "source"):
            conn.execute("ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'adzuna'")
            # Prefix IDs of legacy rows that pre-date multi-source support.
            conn.execute(
                "UPDATE jobs SET id = 'adzuna_' || id WHERE id NOT LIKE 'adzuna_%'"
            )

        # --- scan_log column migrations ---
        if not _column_exists(conn, "scan_log", "source"):
            conn.execute("ALTER TABLE scan_log ADD COLUMN source TEXT DEFAULT ''")

        # --- settings table ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                source TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                keywords TEXT DEFAULT '',
                location TEXT DEFAULT '',
                count INTEGER DEFAULT 50
            )
        """)

        # Seed defaults on first run; INSERT OR IGNORE preserves any saved config.
        defaults = [
            ("adzuna",   1, os.getenv("JOB_SEARCH_KEYWORDS", "remote software engineer"), os.getenv("JOB_SEARCH_LOCATION", ""), 50),
            ("remotive", 0, "software engineer", "", 50),
            ("remoteok", 0, "software engineer", "", 50),
            ("themuse",  0, "software engineer", "", 50),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO settings (source, enabled, keywords, location, count) VALUES (?, ?, ?, ?, ?)",
            defaults,
        )


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def get_existing_ids() -> set[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id FROM jobs").fetchall()
    return {r["id"] for r in rows}


def insert_job(job: dict):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (id, source, title, company, location, description, url,
                 salary_min, salary_max, posted_date, fetched_at,
                 score, summary, match_reasons, analyzed_at)
            VALUES
                (:id, :source, :title, :company, :location, :description, :url,
                 :salary_min, :salary_max, :posted_date, :fetched_at,
                 :score, :summary, :match_reasons, :analyzed_at)
            """,
            {**job, "match_reasons": json.dumps(job.get("match_reasons", []))},
        )


def get_jobs(min_score: int = 0) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE score >= ? ORDER BY score DESC",
            (min_score,),
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["match_reasons"] = json.loads(d["match_reasons"] or "[]")
        d["dismissed"] = bool(d.get("dismissed"))
        results.append(d)
    return results


def get_job_by_id(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["match_reasons"] = json.loads(d["match_reasons"] or "[]")
    d["dismissed"] = bool(d.get("dismissed"))
    return d


def toggle_dismissed(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT dismissed FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return False
        new_val = 0 if row["dismissed"] else 1
        conn.execute("UPDATE jobs SET dismissed = ? WHERE id = ?", (new_val, job_id))
    return bool(new_val)


def toggle_applied(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT applied_at FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        if row["applied_at"]:
            conn.execute("UPDATE jobs SET applied_at = NULL WHERE id = ?", (job_id,))
            return {"applied_at": None}
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE jobs SET applied_at = ? WHERE id = ?", (now, job_id))
        return {"applied_at": now}


# ---------------------------------------------------------------------------
# Scan log
# ---------------------------------------------------------------------------

def log_scan(scanned_at: str, new_jobs_found: int, status: str, source: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scan_log (scanned_at, new_jobs_found, status, source) VALUES (?, ?, ?, ?)",
            (scanned_at, new_jobs_found, status, source),
        )


def get_last_scan() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM scan_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_jobs_today(since: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM jobs WHERE fetched_at >= ?", (since,)
        ).fetchone()
    return row["cnt"]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_all_settings() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM settings ORDER BY source").fetchall()
    return [dict(r) for r in rows]


def save_settings(settings: list[dict]) -> None:
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO settings (source, enabled, keywords, location, count)
            VALUES (:source, :enabled, :keywords, :location, :count)
            """,
            settings,
        )
