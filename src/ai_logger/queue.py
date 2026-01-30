"""SQLite-backed job queue for retry on failure."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings
from .models import SessionEvent


def _get_db_path() -> Path:
    """Get the database path, creating parent dirs if needed."""
    path = get_settings().get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_connection() -> sqlite3.Connection:
    """Get a database connection, creating tables if needed."""
    conn = sqlite3.connect(_get_db_path())
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def enqueue_failed(event: SessionEvent, error: str) -> int:
    """Add a failed job to the queue for later retry."""
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO jobs (event_json, status, error, created_at, updated_at)
        VALUES (?, 'pending', ?, ?, ?)
        """,
        (event.model_dump_json(), error, now, now),
    )
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    if job_id is None:
        raise RuntimeError("Failed to insert job into queue")
    return job_id


def get_pending_jobs(limit: int = 100) -> list[tuple[int, SessionEvent]]:
    """Get pending jobs from the queue."""
    conn = _get_connection()
    cursor = conn.execute(
        """
        SELECT id, event_json FROM jobs
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (limit,),
    )
    jobs = []
    for row in cursor.fetchall():
        event = SessionEvent.model_validate_json(row[1])
        jobs.append((row[0], event))
    conn.close()
    return jobs


def mark_completed(job_id: int) -> None:
    """Mark a job as successfully completed."""
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE jobs SET status = 'completed', updated_at = ? WHERE id = ?",
        (now, job_id),
    )
    conn.commit()
    conn.close()


def mark_failed(job_id: int, error: str) -> None:
    """Mark a job as failed, incrementing retry count."""
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()
    max_retries = get_settings().max_retries

    conn.execute(
        """
        UPDATE jobs
        SET status = CASE WHEN retry_count >= ? THEN 'failed' ELSE 'pending' END,
            error = ?,
            updated_at = ?,
            retry_count = retry_count + 1
        WHERE id = ?
        """,
        (max_retries, error, now, job_id),
    )
    conn.commit()
    conn.close()


def get_queue_status() -> dict[str, int]:
    """Get queue statistics."""
    conn = _get_connection()
    cursor = conn.execute(
        """
        SELECT status, COUNT(*) FROM jobs
        GROUP BY status
        """
    )
    stats = {"pending": 0, "completed": 0, "failed": 0, "total": 0}
    for row in cursor.fetchall():
        stats[row[0]] = row[1]
        stats["total"] += row[1]
    conn.close()
    return stats


def clear_completed(older_than_days: int = 7) -> int:
    """Remove completed jobs older than N days."""
    conn = _get_connection()
    cursor = conn.execute(
        """
        DELETE FROM jobs
        WHERE status = 'completed'
        AND datetime(updated_at) < datetime('now', ?)
        """,
        (f"-{older_than_days} days",),
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count
