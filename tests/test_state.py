"""Tests for session state management."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_logger.state import (
    SessionState,
    get_session_state,
    save_session_state,
    _get_state_dir,
)


class TestSessionState:
    """Tests for SessionState model and persistence."""

    def test_session_state_model(self):
        """Test SessionState model creation."""
        state = SessionState(
            last_log_time=1700000000,
            last_line_count=42,
            last_summary="Implemented user authentication",
        )

        assert state.last_log_time == 1700000000
        assert state.last_line_count == 42
        assert state.last_summary == "Implemented user authentication"

    def test_save_and_load_state(self, temp_dir):
        """Test saving and loading session state."""
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(temp_dir)}):
            session_id = "test-session-123"
            state = SessionState(
                last_log_time=1700000000,
                last_line_count=100,
                last_summary="Added new feature",
            )

            save_session_state(session_id, state)
            loaded = get_session_state(session_id)

            assert loaded is not None
            assert loaded.last_log_time == 1700000000
            assert loaded.last_line_count == 100
            assert loaded.last_summary == "Added new feature"

    def test_get_nonexistent_state(self, temp_dir):
        """Test loading state for a session that doesn't exist."""
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(temp_dir)}):
            result = get_session_state("nonexistent-session")
            assert result is None

    def test_get_corrupted_state(self, temp_dir):
        """Test handling of corrupted state file."""
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(temp_dir)}):
            # Create corrupted state file
            state_dir = _get_state_dir()
            state_file = state_dir / "corrupted-session.json"
            with open(state_file, "w") as f:
                f.write("not valid json")

            result = get_session_state("corrupted-session")
            assert result is None

    def test_state_dir_created(self, temp_dir):
        """Test that state directory is created if it doesn't exist."""
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(temp_dir)}):
            state_dir = _get_state_dir()
            assert state_dir.exists()
            assert state_dir.is_dir()

    def test_update_existing_state(self, temp_dir):
        """Test updating an existing session's state."""
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(temp_dir)}):
            session_id = "update-test"

            # Save initial state
            state1 = SessionState(
                last_log_time=1700000000,
                last_line_count=50,
                last_summary="Initial work",
            )
            save_session_state(session_id, state1)

            # Update with new state
            state2 = SessionState(
                last_log_time=1700001000,
                last_line_count=100,
                last_summary="More work done",
            )
            save_session_state(session_id, state2)

            # Verify updated state
            loaded = get_session_state(session_id)
            assert loaded.last_log_time == 1700001000
            assert loaded.last_line_count == 100
            assert loaded.last_summary == "More work done"

    def test_get_incomplete_state(self, temp_dir):
        """Test handling of state file with missing required fields."""
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(temp_dir)}):
            # Create state file with missing fields (valid JSON but incomplete)
            state_dir = _get_state_dir()
            state_file = state_dir / "incomplete-session.json"
            with open(state_file, "w") as f:
                # Missing last_line_count and last_summary
                f.write('{"last_log_time": 123}')

            result = get_session_state("incomplete-session")
            assert result is None
