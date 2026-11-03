# tracker.py
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "applications.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                external_path TEXT PRIMARY KEY,
                job_url TEXT,
                title TEXT,
                last_applied_at TEXT,
                status TEXT DEFAULT 'applied'
            )
        """)


def get_last_applied(external_path):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT last_applied_at FROM applications WHERE external_path = ?",
            (external_path,),
        ).fetchone()
    return datetime.fromisoformat(row[0]) if row and row[0] else None


def mark_applied(external_path, job_url, title):
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO applications (external_path, job_url, title, last_applied_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(external_path) DO UPDATE SET
                last_applied_at = excluded.last_applied_at,
                job_url = excluded.job_url,
                title = excluded.title
        """, (external_path, job_url, title, now))
    print(f"  💾 Tracker mis à jour : {title}")


def should_apply(external_path, cooldown_hours=48):
    """True s'il n'y a jamais eu de candidature OU si > 48h."""
    last = get_last_applied(external_path)
    if last is None:
        return True
    return datetime.now() - last > timedelta(hours=cooldown_hours)