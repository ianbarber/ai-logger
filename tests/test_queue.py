"""Tests for SQLite job queue."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_logger.models import AgentSource, SessionEvent


@pytest.fixture
def queue_db(temp_dir, mock_settings):
    """Set up a test queue database."""
    # Import after mocking settings
    from ai_logger import queue

    # Patch the db path getter
    with patch.object(queue, "_get_db_path", return_value=temp_dir / "test_queue.db"):
        yield temp_dir / "test_queue.db"


@pytest.fixture
def sample_event():
    """Create a sample session event."""
    return SessionEvent(
        source=AgentSource.CLAUDE_CODE,
        session_id="test-123",
        transcript_path="/tmp/transcript.jsonl",
        cwd="/home/user/project",
        machine="test-machine",
    )


class TestQueue:
    """Tests for job queue operations."""

    def test_enqueue_failed_creates_job(self, queue_db, sample_event):
        """Test that enqueue_failed creates a new job."""
        from ai_logger.queue import enqueue_failed, get_pending_jobs

        job_id = enqueue_failed(sample_event, "Test error")

        assert job_id > 0
        jobs = get_pending_jobs()
        assert len(jobs) == 1
        assert jobs[0][0] == job_id
        assert jobs[0][1].session_id == "test-123"

    def test_mark_completed_updates_status(self, queue_db, sample_event):
        """Test marking a job as completed."""
        from ai_logger.queue import enqueue_failed, mark_completed, get_queue_status

        job_id = enqueue_failed(sample_event, "Error")
        mark_completed(job_id)

        status = get_queue_status()
        assert status["completed"] == 1
        assert status["pending"] == 0

    def test_mark_failed_increments_retry_count(self, queue_db, sample_event):
        """Test that mark_failed increments retry count."""
        from ai_logger.queue import enqueue_failed, mark_failed, _get_connection

        job_id = enqueue_failed(sample_event, "Error 1")
        mark_failed(job_id, "Error 2")

        conn = _get_connection()
        cursor = conn.execute("SELECT retry_count, status FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 1  # retry_count incremented
        assert row[1] == "pending"  # still pending (under max retries)

    def test_mark_failed_marks_as_failed_after_max_retries(self, queue_db, sample_event):
        """Test that job is marked failed after max retries."""
        from unittest.mock import MagicMock
        from ai_logger.queue import enqueue_failed, mark_failed, get_queue_status

        # Create a mock settings with max_retries = 2
        mock_settings = MagicMock()
        mock_settings.max_retries = 2

        with patch("ai_logger.queue.get_settings", return_value=mock_settings):
            job_id = enqueue_failed(sample_event, "Error 1")
            mark_failed(job_id, "Error 2")  # retry 1
            mark_failed(job_id, "Error 3")  # retry 2
            mark_failed(job_id, "Error 4")  # retry 3 -> exceeds max

            status = get_queue_status()
            assert status["failed"] == 1
            assert status["pending"] == 0

    def test_get_pending_jobs_respects_limit(self, queue_db, sample_event):
        """Test that get_pending_jobs respects the limit parameter."""
        from ai_logger.queue import enqueue_failed, get_pending_jobs

        # Create 5 jobs
        for i in range(5):
            event = SessionEvent(
                source=AgentSource.CLAUDE_CODE,
                session_id=f"test-{i}",
                transcript_path="/tmp/test.jsonl",
                cwd="/tmp",
                machine="test",
            )
            enqueue_failed(event, f"Error {i}")

        jobs = get_pending_jobs(limit=3)
        assert len(jobs) == 3

    def test_get_queue_status(self, queue_db, sample_event):
        """Test queue status reporting."""
        from ai_logger.queue import enqueue_failed, mark_completed, get_queue_status

        # Create some jobs with different statuses
        id1 = enqueue_failed(sample_event, "Error 1")
        id2 = enqueue_failed(sample_event, "Error 2")
        mark_completed(id1)

        status = get_queue_status()
        assert status["pending"] == 1
        assert status["completed"] == 1
        assert status["total"] == 2

    def test_clear_completed_removes_old_jobs(self, queue_db, sample_event):
        """Test clearing old completed jobs."""
        from ai_logger.queue import enqueue_failed, mark_completed, clear_completed, _get_connection

        job_id = enqueue_failed(sample_event, "Error")
        mark_completed(job_id)

        # Manually backdate the job
        conn = _get_connection()
        conn.execute(
            "UPDATE jobs SET updated_at = datetime('now', '-10 days') WHERE id = ?",
            (job_id,),
        )
        conn.commit()
        conn.close()

        removed = clear_completed(older_than_days=7)
        assert removed == 1
