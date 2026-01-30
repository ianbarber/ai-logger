"""Tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ai_logger.cli import main


@pytest.fixture
def cli_runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestLogCommand:
    """Tests for the log command."""

    def test_log_requires_all_options(self, cli_runner):
        """Test that log command requires all mandatory options."""
        result = cli_runner.invoke(main, ["log"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output

    def test_log_with_valid_options(self, cli_runner, temp_dir):
        """Test log command with valid options."""
        # Create a minimal transcript file
        transcript = temp_dir / "test.jsonl"
        transcript.write_text('{"type": "user", "message": {"role": "user", "content": "test"}}')

        with patch("ai_logger.pipeline.process_session") as mock_process:
            mock_process.return_value = "block-123"

            result = cli_runner.invoke(
                main,
                [
                    "log",
                    "--source", "claude-code",
                    "--session-id", "test-123",
                    "--transcript", str(transcript),
                    "--cwd", "/tmp/project",
                    "--machine", "test-machine",
                ],
            )

            assert result.exit_code == 0
            assert "logged successfully" in result.output
            mock_process.assert_called_once()

    def test_log_queues_on_failure(self, cli_runner, temp_dir):
        """Test that failures are queued for retry."""
        transcript = temp_dir / "test.jsonl"
        transcript.write_text('{"type": "user", "message": {"role": "user", "content": "test"}}')

        with patch("ai_logger.pipeline.process_session") as mock_process:
            mock_process.side_effect = Exception("API error")

            with patch("ai_logger.queue.enqueue_failed") as mock_enqueue:
                result = cli_runner.invoke(
                    main,
                    [
                        "log",
                        "--source", "claude-code",
                        "--session-id", "test-123",
                        "--transcript", str(transcript),
                        "--cwd", "/tmp/project",
                        "--machine", "test-machine",
                    ],
                )

                assert "queued for retry" in result.output
                mock_enqueue.assert_called_once()


class TestRetryCommand:
    """Tests for the retry command."""

    def test_retry_no_pending_jobs(self, cli_runner):
        """Test retry when no jobs are pending."""
        with patch("ai_logger.queue.get_pending_jobs", return_value=[]):
            result = cli_runner.invoke(main, ["retry"])

            assert result.exit_code == 0
            assert "No pending jobs" in result.output

    def test_retry_processes_jobs(self, cli_runner, sample_session_event):
        """Test retry processes pending jobs."""
        with patch("ai_logger.queue.get_pending_jobs") as mock_get:
            mock_get.return_value = [(1, sample_session_event)]

            with patch("ai_logger.pipeline.process_session") as mock_process:
                with patch("ai_logger.queue.mark_completed") as mock_complete:
                    result = cli_runner.invoke(main, ["retry"])

                    assert result.exit_code == 0
                    assert "1 succeeded" in result.output
                    mock_complete.assert_called_once_with(1)

    def test_retry_quiet_mode(self, cli_runner):
        """Test retry with quiet flag."""
        with patch("ai_logger.queue.get_pending_jobs", return_value=[]):
            result = cli_runner.invoke(main, ["retry", "--quiet"])

            assert result.exit_code == 0
            assert result.output == ""


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_shows_counts(self, cli_runner):
        """Test status shows queue counts."""
        with patch("ai_logger.queue.get_queue_status") as mock_status:
            mock_status.return_value = {"pending": 5, "failed": 2, "completed": 10, "total": 17}

            result = cli_runner.invoke(main, ["status"])

            assert result.exit_code == 0
            assert "Pending: 5" in result.output
            assert "Failed:  2" in result.output
            assert "Total:   17" in result.output
