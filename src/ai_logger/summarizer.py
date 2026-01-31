"""Claude CLI client for transcript summarization."""

import json
import os
import subprocess
import re

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import (
    ArtifactInfo,
    ParsedTranscript,
    PRInfo,
    ServiceInfo,
    SessionEvent,
    SessionSummary,
)

TRIVIALITY_CHECK_PROMPT = """Is this coding session worth logging? Consider:
- Just browsing/reading files without changes = NOT worth logging
- Abandoned/incomplete work with no output = NOT worth logging
- Very short with no meaningful activity = NOT worth logging
- Actual code changes, PRs, or substantial work = WORTH logging

<transcript>
{transcript_content}
</transcript>

Reply with EXACTLY "YES" or "NO" followed by a 5-word reason.
Example: "NO Just browsed files briefly" or "YES Implemented new authentication feature"
"""

SUMMARIZATION_PROMPT = """You are analyzing an AI coding session transcript. Extract a structured summary.

<transcript>
{transcript_content}
</transcript>

<context>
Machine: {machine}
Project: {project_path}
Agent: {agent_type}
</context>

Return a JSON object with these fields:
- "summary": 1-2 sentence description of what was accomplished
- "prs": Array of {{"url": "...", "title": "...", "action": "created|updated|reviewed"}}
- "services": Array of {{"name": "...", "action": "started|deployed|stopped"}}
- "artifacts": Array of {{"type": "file|config|script", "path": "...", "description": "..."}}

Rules:
- Be concise - this is a log entry, not documentation
- Only include PRs with actual GitHub URLs from the transcript
- Only include services that were explicitly started/deployed
- Artifacts = notable files created (not every file touched)
- If nothing notable happened, say so briefly

Return ONLY valid JSON, no markdown or explanation."""


class SummarizationError(Exception):
    """Error during summarization."""

    pass


class RetryableError(Exception):
    """Error that should trigger a retry."""

    pass


def _truncate_transcript(transcript: ParsedTranscript, max_chars: int = 100000) -> str:
    """Truncate transcript to fit within character limit."""
    if len(transcript.raw_text) <= max_chars:
        return transcript.raw_text

    # Take the last N characters to keep most recent context
    truncated = transcript.raw_text[-max_chars:]

    # Try to start at a message boundary
    first_user = truncated.find("\n\nUser: ")
    first_assistant = truncated.find("\n\nAssistant: ")
    boundaries = [x for x in [first_user, first_assistant] if x > 0]
    first_boundary = min(boundaries) if boundaries else 0

    return "[...truncated...]\n" + truncated[first_boundary:]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(RetryableError),
)
def summarize_transcript(
    transcript: ParsedTranscript,
    event: SessionEvent,
) -> SessionSummary:
    """Summarize a transcript using Claude CLI.

    Uses `claude -p` to call Claude Code in print mode, avoiding
    the need for a separate API key.

    Args:
        transcript: Parsed transcript to summarize
        event: Session event with metadata

    Returns:
        SessionSummary with extracted information

    Raises:
        SummarizationError: If summarization fails permanently
        RetryableError: If summarization fails but should be retried
    """
    # Truncate if needed
    content = _truncate_transcript(transcript)

    prompt = SUMMARIZATION_PROMPT.format(
        transcript_content=content,
        machine=event.machine,
        project_path=event.cwd,
        agent_type=event.source.value,
    )

    try:
        # Set AI_LOGGER_RUNNING to prevent exit hooks from triggering
        # another summarization (which would cause infinite recursion)
        env = {**os.environ, "AI_LOGGER_RUNNING": "1"}

        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "rate" in stderr.lower() or "limit" in stderr.lower():
                raise RetryableError(f"Rate limited: {stderr}")
            raise SummarizationError(f"Claude CLI error: {stderr}")

        response_text = result.stdout.strip()

    except subprocess.TimeoutExpired:
        raise RetryableError("Claude CLI timed out")
    except FileNotFoundError:
        raise SummarizationError(
            "Claude CLI not found. Make sure 'claude' is installed and in PATH."
        )
    except subprocess.SubprocessError as e:
        raise SummarizationError(f"Subprocess error: {e}")

    return _parse_summary_response(response_text)


def is_session_trivial(transcript: ParsedTranscript) -> tuple[bool, str]:
    """Check if a session is trivial and not worth logging.

    Uses Haiku for a fast, cheap check before running full summarization.

    Args:
        transcript: Parsed transcript to check

    Returns:
        Tuple of (is_trivial, reason). If trivial, the session should be skipped.
    """
    # Very short transcripts are trivial by definition
    if transcript.token_estimate < 100:
        return True, "Session too short"

    content = _truncate_transcript(transcript, max_chars=10000)  # Smaller for haiku
    prompt = TRIVIALITY_CHECK_PROMPT.format(transcript_content=content)

    try:
        env = {**os.environ, "AI_LOGGER_RUNNING": "1"}

        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "haiku", "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        if result.returncode != 0:
            # If haiku check fails, assume non-trivial to be safe
            return False, "Triviality check failed"

        response = result.stdout.strip().upper()

        # Parse YES/NO response
        if response.startswith("NO"):
            reason = result.stdout.strip()[3:].strip() or "Trivial activity"
            return True, reason
        elif response.startswith("YES"):
            reason = result.stdout.strip()[4:].strip() or "Worth logging"
            return False, reason
        else:
            # Unclear response, assume non-trivial
            return False, "Unclear triviality check"

    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        # On any error, assume non-trivial to be safe
        return False, "Triviality check error"


def _parse_summary_response(response_text: str) -> SessionSummary:
    """Parse the JSON response from Claude into a SessionSummary."""
    text = response_text.strip()

    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # Try to find JSON object in the response (handles nested objects)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                raise SummarizationError(f"Failed to parse JSON response: {e}")
        else:
            raise SummarizationError(f"No JSON found in response: {e}")

    # Build SessionSummary from parsed data
    prs = [
        PRInfo(url=pr["url"], title=pr.get("title", ""), action=pr.get("action", "created"))
        for pr in data.get("prs", [])
        if isinstance(pr, dict) and "url" in pr
    ]

    services = [
        ServiceInfo(name=svc["name"], action=svc.get("action", "started"))
        for svc in data.get("services", [])
        if isinstance(svc, dict) and "name" in svc
    ]

    artifacts = [
        ArtifactInfo(
            type=art.get("type", "file"),
            path=art.get("path", ""),
            description=art.get("description", ""),
        )
        for art in data.get("artifacts", [])
        if isinstance(art, dict)
    ]

    return SessionSummary(
        summary=data.get("summary", "No summary available"),
        prs=prs,
        services=services,
        artifacts=artifacts,
    )
