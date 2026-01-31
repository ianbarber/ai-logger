"""Tests for transcript parsers."""

import json
from pathlib import Path

import pytest

from ai_logger.parsers.claude_code import parse_claude_code_transcript
from ai_logger.parsers.codex import parse_codex_history


class TestClaudeCodeParser:
    """Tests for Claude Code JSONL parser."""

    def test_parse_basic_transcript(self, sample_claude_transcript):
        """Test parsing a basic transcript with user and assistant messages."""
        result = parse_claude_code_transcript(sample_claude_transcript)

        assert len(result.messages) == 4
        assert result.messages[0].role == "user"
        assert "Python project" in result.messages[0].content
        assert result.messages[1].role == "assistant"
        assert "Tool: Bash" in result.messages[1].content

    def test_parse_extracts_raw_text(self, sample_claude_transcript):
        """Test that raw text is properly formatted for summarization."""
        result = parse_claude_code_transcript(sample_claude_transcript)

        assert "User: Help me create a new Python project" in result.raw_text
        assert "Assistant:" in result.raw_text
        assert result.token_estimate > 0

    def test_parse_handles_empty_file(self, temp_dir):
        """Test parsing an empty file."""
        empty_file = temp_dir / "empty.jsonl"
        empty_file.touch()

        result = parse_claude_code_transcript(empty_file)

        assert len(result.messages) == 0
        assert result.raw_text == ""

    def test_parse_handles_malformed_json(self, temp_dir):
        """Test that malformed JSON lines are skipped."""
        bad_file = temp_dir / "bad.jsonl"
        with open(bad_file, "w") as f:
            f.write('{"type": "user", "message": {"role": "user", "content": "valid"}}\n')
            f.write("this is not json\n")
            f.write('{"type": "user", "message": {"role": "user", "content": "also valid"}}\n')

        result = parse_claude_code_transcript(bad_file)

        assert len(result.messages) == 2

    def test_parse_skips_non_message_types(self, temp_dir):
        """Test that non-message entry types are skipped."""
        mixed_file = temp_dir / "mixed.jsonl"
        with open(mixed_file, "w") as f:
            f.write('{"type": "file-history-snapshot", "data": {}}\n')
            f.write('{"type": "user", "message": {"role": "user", "content": "hello"}}\n')
            f.write('{"type": "thinking", "content": "internal"}\n')

        result = parse_claude_code_transcript(mixed_file)

        assert len(result.messages) == 1
        assert result.messages[0].content == "hello"

    def test_parse_handles_list_content(self, temp_dir):
        """Test parsing messages with list-style content blocks."""
        list_content_file = temp_dir / "list.jsonl"
        entry = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "internal thought"},
                    {"type": "text", "text": "I'll help you."},
                    {"type": "tool_use", "name": "Read", "input": {"path": "/file"}},
                ],
            },
        }
        with open(list_content_file, "w") as f:
            f.write(json.dumps(entry) + "\n")

        result = parse_claude_code_transcript(list_content_file)

        assert len(result.messages) == 1
        assert "I'll help you" in result.messages[0].content
        assert "Tool: Read" in result.messages[0].content

    def test_parse_returns_total_lines(self, sample_claude_transcript):
        """Test that total_lines is returned for incremental logging."""
        result = parse_claude_code_transcript(sample_claude_transcript)

        # Sample transcript has 4 entries
        assert result.total_lines == 4

    def test_parse_with_start_line_offset(self, sample_claude_transcript):
        """Test parsing from a specific line offset."""
        # Parse full transcript first
        full_result = parse_claude_code_transcript(sample_claude_transcript)
        assert len(full_result.messages) == 4

        # Parse starting from line 2 (skip first 2 lines)
        partial_result = parse_claude_code_transcript(sample_claude_transcript, start_line=2)

        # Should only have the last 2 messages
        assert len(partial_result.messages) == 2
        # But total_lines should still reflect the full file
        assert partial_result.total_lines == 4

    def test_parse_with_offset_beyond_file(self, sample_claude_transcript):
        """Test parsing with offset beyond file length."""
        result = parse_claude_code_transcript(sample_claude_transcript, start_line=100)

        # Should return empty result
        assert len(result.messages) == 0
        # total_lines should still be the file length
        assert result.total_lines == 4


class TestCodexParser:
    """Tests for Codex CLI history parser."""

    def test_parse_full_history(self, sample_codex_history):
        """Test parsing all entries from history."""
        result = parse_codex_history(sample_codex_history)

        assert len(result.messages) == 3
        assert all(m.role == "user" for m in result.messages)
        assert "REST API" in result.messages[0].content

    def test_parse_filters_by_session(self, sample_codex_history):
        """Test filtering by session ID."""
        result = parse_codex_history(sample_codex_history, session_id="codex-session-1")

        assert len(result.messages) == 2
        assert "REST API" in result.messages[0].content
        assert "authentication" in result.messages[1].content

    def test_parse_empty_file(self, temp_dir):
        """Test parsing empty history file."""
        empty_file = temp_dir / "empty.jsonl"
        empty_file.touch()

        result = parse_codex_history(empty_file)

        assert len(result.messages) == 0

    def test_parse_builds_raw_text(self, sample_codex_history):
        """Test that raw text is built for summarization."""
        result = parse_codex_history(sample_codex_history, session_id="codex-session-1")

        assert "User: Create a REST API" in result.raw_text
        assert result.token_estimate > 0
