"""Session state management for incremental logging."""

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class SessionState(BaseModel):
    """Persisted state for a session to support incremental logging."""

    last_log_time: int  # Unix timestamp
    last_line_count: int  # Lines in transcript at last log
    last_summary: str  # One-liner for context in subsequent logs


def _get_state_dir() -> Path:
    """Get the state directory, creating it if needed."""
    import os

    state_home = os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    state_dir = Path(state_home) / "ai-logger" / "sessions"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _get_state_path(session_id: str) -> Path:
    """Get the state file path for a session."""
    return _get_state_dir() / f"{session_id}.json"


def get_session_state(session_id: str) -> Optional[SessionState]:
    """Load session state if it exists.

    Args:
        session_id: The session identifier

    Returns:
        SessionState if found, None otherwise
    """
    state_path = _get_state_path(session_id)
    if not state_path.exists():
        return None

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SessionState(**data)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        # Corrupted state file, treat as no state
        # ValueError catches Pydantic ValidationError (which inherits from it)
        return None


def save_session_state(session_id: str, state: SessionState) -> None:
    """Save session state.

    Args:
        session_id: The session identifier
        state: The state to save
    """
    state_path = _get_state_path(session_id)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state.model_dump(), f)
