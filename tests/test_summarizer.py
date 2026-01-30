"""Tests for Claude CLI summarizer."""

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_logger.models import (
    AgentSource,
    ParsedTranscript,
    SessionEvent,
    TranscriptMessage,
)
from ai_logger.summarizer import (
    _parse_summary_response,
    _truncate_transcript,
    summarize_transcript,
    SummarizationError,
)


@pytest.fixture
def sample_transcript():
    """Create a sample parsed transcript."""
    messages = [
        TranscriptMessage(role="user", content="Create a new API endpoint"),
        TranscriptMessage(role="assistant", content="I'll create the endpoint for you."),
    ]
    return ParsedTranscript(
        messages=messages,
        raw_text="User: Create a new API endpoint\n\nAssistant: I'll create the endpoint for you.",
        token_estimate=50,
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
    )


class TestTruncateTranscript:
    """Tests for transcript truncation."""

    def test_no_truncation_needed(self):
        """Test that short transcripts aren't truncated."""
        transcript = ParsedTranscript(
            messages=[],
            raw_text="Short content",
            token_estimate=100,
        )
        result = _truncate_transcript(transcript, max_chars=10000)
        assert result == "Short content"

    def test_truncates_long_transcripts(self):
        """Test truncation of long transcripts."""
        long_text = "User: " + "a" * 100000 + "\n\nAssistant: response"
        transcript = ParsedTranscript(
            messages=[],
            raw_text=long_text,
            token_estimate=30000,
        )
        result = _truncate_transcript(transcript, max_chars=5000)

        assert len(result) < len(long_text)
        assert "[...truncated...]" in result


class TestParseSummaryResponse:
    """Tests for parsing Claude's JSON responses."""

    def test_parse_valid_json(self):
        """Test parsing a valid JSON response."""
        response = json.dumps({
            "summary": "Created a new API endpoint",
            "prs": [{"url": "https://github.com/user/repo/pull/1", "title": "Add endpoint"}],
            "services": [],
            "artifacts": [],
        })

        result = _parse_summary_response(response)

        assert result.summary == "Created a new API endpoint"
        assert len(result.prs) == 1
        assert result.prs[0].url == "https://github.com/user/repo/pull/1"

    def test_parse_json_in_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = """```json
{
    "summary": "Fixed a bug",
    "prs": [],
    "services": [],
    "artifacts": []
}
```"""

        result = _parse_summary_response(response)
        assert result.summary == "Fixed a bug"

    def test_parse_handles_missing_fields(self):
        """Test parsing response with missing optional fields."""
        response = json.dumps({"summary": "Did some work"})

        result = _parse_summary_response(response)

        assert result.summary == "Did some work"
        assert result.prs == []
        assert result.services == []

    def test_parse_raises_on_invalid_json(self):
        """Test that invalid JSON raises an error."""
        with pytest.raises(SummarizationError):
            _parse_summary_response("not valid json at all")

    def test_parse_extracts_json_from_mixed_content(self):
        """Test extracting JSON from response with extra text."""
        response = 'Here is the summary: {"summary": "Work done", "prs": []}'

        result = _parse_summary_response(response)
        assert result.summary == "Work done"


class TestSummarizeTranscript:
    """Tests for the main summarization function."""

    def test_summarize_calls_claude_cli(self, sample_transcript, sample_event):
        """Test that summarize_transcript calls the Claude CLI correctly."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "summary": "Created API endpoint",
            "prs": [],
            "services": [],
            "artifacts": [],
        })
        mock_result.stderr = ""

        with patch("ai_logger.summarizer.subprocess.run", return_value=mock_result) as mock_run:
            result = summarize_transcript(sample_transcript, sample_event)

            assert result.summary == "Created API endpoint"
            mock_run.assert_called_once()
            # Verify claude CLI was called with -p flag
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "claude"
            assert "-p" in call_args

    def test_summarize_includes_context(self, sample_transcript, sample_event):
        """Test that context is included in the prompt."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "summary": "Test",
            "prs": [],
            "services": [],
            "artifacts": [],
        })
        mock_result.stderr = ""

        with patch("ai_logger.summarizer.subprocess.run", return_value=mock_result) as mock_run:
            summarize_transcript(sample_transcript, sample_event)

            call_args = mock_run.call_args[0][0]
            prompt = call_args[2]  # The prompt is the third argument after "claude" and "-p"

            assert "test-laptop" in prompt  # machine name
            assert "/home/user/project" in prompt  # cwd
            assert "claude-code" in prompt  # agent type
