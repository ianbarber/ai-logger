"""Parser for Codex CLI history."""

import json
from pathlib import Path

from ..models import ParsedTranscript, TranscriptMessage


def parse_codex_history(
    history_path: Path,
    session_id: str | None = None,
) -> ParsedTranscript:
    """Parse Codex CLI history file.

    Codex stores history as JSONL with entries containing:
    - session_id: Session identifier
    - ts: Unix timestamp
    - text: The prompt/message text

    Args:
        history_path: Path to the history.jsonl file
        session_id: If provided, only include messages from this session

    Returns:
        ParsedTranscript with messages and raw text for summarization

    Raises:
        FileNotFoundError: If history file does not exist
        PermissionError: If history file cannot be read
    """
    if not history_path.exists():
        raise FileNotFoundError(f"History file not found: {history_path}")

    messages: list[TranscriptMessage] = []
    raw_parts: list[str] = []

    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filter by session if specified
            if session_id and entry.get("session_id") != session_id:
                continue

            text = entry.get("text", "")
            if not text:
                continue

            # Codex history only contains user prompts
            messages.append(
                TranscriptMessage(
                    role="user",
                    content=text,
                )
            )
            raw_parts.append(f"User: {text}")

    raw_text = "\n\n".join(raw_parts)
    token_estimate = len(raw_text) // 4

    return ParsedTranscript(
        messages=messages,
        raw_text=raw_text,
        token_estimate=token_estimate,
    )


def find_codex_history() -> Path | None:
    """Find the default Codex history file."""
    default_path = Path.home() / ".codex" / "history.jsonl"
    if default_path.exists():
        return default_path
    return None
