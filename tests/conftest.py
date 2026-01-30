"""Pytest fixtures for ai-logger tests."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_settings(temp_dir):
    """Mock settings for tests."""
    with patch.dict(os.environ, {
        "ROAM_GRAPH_NAME": "test-graph",
        "ROAM_API_TOKEN": "test-roam-token",
    }):
        from ai_logger.config import Settings
        settings = Settings(db_path=temp_dir / "queue.db")
        with patch("ai_logger.config.get_settings", return_value=settings):
            yield settings


@pytest.fixture
def sample_claude_transcript(temp_dir) -> Path:
    """Create a sample Claude Code transcript file."""
    transcript_path = temp_dir / "session.jsonl"
    entries = [
        {
            "type": "user",
            "message": {"role": "user", "content": "Help me create a new Python project"},
            "sessionId": "test-session-123",
            "uuid": "msg-1",
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll help you create a Python project."},
                    {"type": "tool_use", "name": "Bash", "input": {"command": "mkdir myproject"}},
                ],
            },
            "sessionId": "test-session-123",
            "uuid": "msg-2",
        },
        {
            "type": "user",
            "message": {"role": "user", "content": "Now create a PR for this"},
            "sessionId": "test-session-123",
            "uuid": "msg-3",
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Created PR: https://github.com/user/repo/pull/42",
                    },
                ],
            },
            "sessionId": "test-session-123",
            "uuid": "msg-4",
        },
    ]

    with open(transcript_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return transcript_path


@pytest.fixture
def sample_codex_history(temp_dir) -> Path:
    """Create a sample Codex history file."""
    history_path = temp_dir / "history.jsonl"
    entries = [
        {
            "session_id": "codex-session-1",
            "ts": 1700000000,
            "text": "Create a REST API endpoint for users",
        },
        {
            "session_id": "codex-session-1",
            "ts": 1700000100,
            "text": "Add authentication middleware",
        },
        {
            "session_id": "codex-session-2",
            "ts": 1700001000,
            "text": "Different session prompt",
        },
    ]

    with open(history_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return history_path


@pytest.fixture
def sample_session_event():
    """Create a sample session event."""
    from ai_logger.models import AgentSource, SessionEvent

    return SessionEvent(
        source=AgentSource.CLAUDE_CODE,
        session_id="test-session-123",
        transcript_path="/tmp/test.jsonl",
        cwd="/home/user/projects/myproject",
        machine="test-laptop",
        tmux_session="dev:0",
    )
