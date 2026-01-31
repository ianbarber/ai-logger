"""Main processing pipeline for session logging."""

import time
from pathlib import Path
from typing import Optional

from .models import AgentSource, SessionEvent, SessionSummary
from .parsers.claude_code import parse_claude_code_transcript
from .parsers.codex import parse_codex_history
from .summarizer import summarize_transcript, is_session_trivial
from .roam import publish_to_roam
from .state import get_session_state, save_session_state, SessionState


class SessionSkipped(Exception):
    """Raised when a session is skipped (no new content or trivial)."""

    pass


def process_session(event: SessionEvent) -> str:
    """Process a session event end-to-end with incremental logging support.

    1. Load session state (if exists)
    2. Parse transcript with offset (only new content)
    3. If no new content or very short, skip
    4. Run haiku triviality check on new content
    5. If trivial, skip
    6. Run full summarization with context from previous summary
    7. Save updated state
    8. Publish to Roam

    Args:
        event: Session event from hook

    Returns:
        UID of the created Roam block

    Raises:
        SessionSkipped: If session has no new content or is trivial
        Various exceptions if any step fails
    """
    transcript_path = Path(event.transcript_path)

    # Load previous session state
    state = get_session_state(event.session_id)
    start_line = state.last_line_count if state else 0
    previous_summary = state.last_summary if state else None

    # Parse transcript based on source (with offset for incremental)
    if event.source == AgentSource.CLAUDE_CODE:
        transcript = parse_claude_code_transcript(transcript_path, start_line=start_line)
    elif event.source == AgentSource.CODEX:
        # Codex parser doesn't support incremental yet
        transcript = parse_codex_history(transcript_path, event.session_id)
    else:
        raise ValueError(f"Unknown source: {event.source}")

    # Skip if no new content
    if not transcript.messages:
        raise SessionSkipped("No new content since last log")

    # Skip if transcript is too short
    if transcript.token_estimate < 50:
        raise SessionSkipped("New content too short to log")

    # Run haiku triviality check
    is_trivial, reason = is_session_trivial(transcript)
    if is_trivial:
        raise SessionSkipped(f"Trivial session: {reason}")

    # Add context from previous summary if this is an incremental log
    raw_text_for_summary = transcript.raw_text
    if previous_summary:
        context_prefix = f"[Continuing session. Previous: {previous_summary}]\n\n"
        raw_text_for_summary = context_prefix + transcript.raw_text

    # Create a copy with the context-augmented raw_text for summarization
    transcript_for_summary = transcript.model_copy(update={"raw_text": raw_text_for_summary})

    # Summarize with Claude
    summary = summarize_transcript(transcript_for_summary, event)

    # Publish to Roam
    block_uid = publish_to_roam(event, summary)

    # Save updated state
    new_state = SessionState(
        last_log_time=int(time.time()),
        last_line_count=transcript.total_lines,
        last_summary=summary.summary,
    )
    save_session_state(event.session_id, new_state)

    return block_uid
