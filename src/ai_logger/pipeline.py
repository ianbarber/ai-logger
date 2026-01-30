"""Main processing pipeline for session logging."""

from pathlib import Path

from .models import AgentSource, SessionEvent
from .parsers.claude_code import parse_claude_code_transcript
from .parsers.codex import parse_codex_history
from .summarizer import summarize_transcript
from .roam import publish_to_roam


def process_session(event: SessionEvent) -> str:
    """Process a session event end-to-end.

    1. Parse the transcript
    2. Summarize with Claude
    3. Publish to Roam

    Args:
        event: Session event from hook

    Returns:
        UID of the created Roam block

    Raises:
        Various exceptions if any step fails
    """
    transcript_path = Path(event.transcript_path)

    # Parse transcript based on source
    if event.source == AgentSource.CLAUDE_CODE:
        transcript = parse_claude_code_transcript(transcript_path)
    elif event.source == AgentSource.CODEX:
        transcript = parse_codex_history(transcript_path, event.session_id)
    else:
        raise ValueError(f"Unknown source: {event.source}")

    # Skip if transcript is empty or very short
    if not transcript.messages or transcript.token_estimate < 50:
        # Still log something minimal
        from .models import SessionSummary
        summary = SessionSummary(summary="Brief session with minimal activity")
    else:
        # Summarize with Claude
        summary = summarize_transcript(transcript, event)

    # Publish to Roam
    block_uid = publish_to_roam(event, summary)

    return block_uid
