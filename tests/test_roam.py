"""Tests for Roam Research publisher."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ai_logger.models import (
    AgentSource,
    ArtifactInfo,
    PRInfo,
    ServiceInfo,
    SessionEvent,
    SessionSummary,
)
from ai_logger.roam import (
    _format_roam_blocks,
    _get_daily_page_title,
    publish_to_roam,
    RoamError,
    RetryableRoamError,
)


@pytest.fixture
def sample_event():
    """Create a sample session event."""
    return SessionEvent(
        source=AgentSource.CLAUDE_CODE,
        session_id="test-123",
        transcript_path="/tmp/test.jsonl",
        cwd="/home/user/project",
        machine="test-laptop",
        tmux_session="dev:0",
    )


@pytest.fixture
def sample_summary():
    """Create a sample session summary."""
    return SessionSummary(
        summary="Implemented user authentication with JWT tokens",
        prs=[
            PRInfo(url="https://github.com/user/repo/pull/42", title="Add auth", action="created")
        ],
        services=[ServiceInfo(name="api-server", action="restarted")],
        artifacts=[
            ArtifactInfo(type="file", path="src/auth.py", description="Auth module")
        ],
    )


class TestGetDailyPageTitle:
    """Tests for daily page title formatting."""

    def test_formats_date_correctly(self):
        """Test that date is formatted in Roam style."""
        with patch("ai_logger.roam.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 26)
            result = _get_daily_page_title()
            assert result == "January 26th, 2026"

    def test_handles_day_suffixes(self):
        """Test correct suffixes for different days."""
        test_cases = [
            (1, "1st"),
            (2, "2nd"),
            (3, "3rd"),
            (4, "4th"),
            (11, "11th"),
            (12, "12th"),
            (13, "13th"),
            (21, "21st"),
            (22, "22nd"),
            (23, "23rd"),
        ]

        for day, expected_suffix in test_cases:
            with patch("ai_logger.roam.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 1, day)
                result = _get_daily_page_title()
                assert expected_suffix in result, f"Failed for day {day}"


class TestFormatRoamBlocks:
    """Tests for block formatting."""

    def test_formats_main_block(self, sample_event, sample_summary):
        """Test main block formatting."""
        blocks = _format_roam_blocks(sample_event, sample_summary)

        assert len(blocks) == 1
        main_block = blocks[0]["string"]

        assert "test-laptop" in main_block
        assert "[[claude-code]]" in main_block

    def test_includes_metadata(self, sample_event, sample_summary):
        """Test that metadata is included as child blocks."""
        blocks = _format_roam_blocks(sample_event, sample_summary)
        children = blocks[0]["children"]

        child_strings = [c["string"] for c in children]

        assert any("project::" in s for s in child_strings)
        assert any("tmux::" in s for s in child_strings)
        assert any("/home/user/project" in s for s in child_strings)

    def test_includes_summary(self, sample_event, sample_summary):
        """Test that summary is included."""
        blocks = _format_roam_blocks(sample_event, sample_summary)
        children = blocks[0]["children"]
        child_strings = [c["string"] for c in children]

        assert any("JWT tokens" in s for s in child_strings)

    def test_includes_prs(self, sample_event, sample_summary):
        """Test that PRs are formatted correctly."""
        blocks = _format_roam_blocks(sample_event, sample_summary)
        children = blocks[0]["children"]
        child_strings = [c["string"] for c in children]

        assert any("#PR" in s and "github.com" in s for s in child_strings)

    def test_includes_services(self, sample_event, sample_summary):
        """Test that services are formatted correctly."""
        blocks = _format_roam_blocks(sample_event, sample_summary)
        children = blocks[0]["children"]
        child_strings = [c["string"] for c in children]

        assert any("#service" in s and "api-server" in s for s in child_strings)

    def test_skips_empty_tmux(self, sample_summary):
        """Test that tmux is skipped when not set."""
        event = SessionEvent(
            source=AgentSource.CLAUDE_CODE,
            session_id="test",
            transcript_path="/tmp/test.jsonl",
            cwd="/tmp",
            machine="test",
            tmux_session="none",
        )

        blocks = _format_roam_blocks(event, sample_summary)
        children = blocks[0]["children"]
        child_strings = [c["string"] for c in children]

        assert not any("tmux::" in s for s in child_strings)


class TestPublishToRoam:
    """Tests for Roam API publishing."""

    def test_publish_success(self, sample_event, sample_summary, mock_settings):
        """Test successful publish to Roam."""
        with patch("ai_logger.roam.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"uid": "block-123"}
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = publish_to_roam(sample_event, sample_summary)

            assert result == "block-123"

    def test_publish_rate_limited_retries(self, sample_event, sample_summary, mock_settings):
        """Test that rate limiting triggers retry."""
        with patch("ai_logger.roam.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            with pytest.raises(RetryableRoamError):
                # Disable retries for test
                publish_to_roam.__wrapped__(sample_event, sample_summary)

    def test_publish_server_error_retries(self, sample_event, sample_summary, mock_settings):
        """Test that server errors trigger retry."""
        with patch("ai_logger.roam.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            with pytest.raises(RetryableRoamError):
                publish_to_roam.__wrapped__(sample_event, sample_summary)

    def test_publish_client_error_fails(self, sample_event, sample_summary, mock_settings):
        """Test that client errors fail immediately."""
        with patch("ai_logger.roam.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad request"
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            with pytest.raises(RoamError):
                publish_to_roam.__wrapped__(sample_event, sample_summary)

    def test_publish_timeout_retries(self, sample_event, sample_summary, mock_settings):
        """Test that timeouts trigger retry."""
        with patch("ai_logger.roam.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = (
                httpx.TimeoutException("timeout")
            )

            with pytest.raises(RetryableRoamError):
                publish_to_roam.__wrapped__(sample_event, sample_summary)
