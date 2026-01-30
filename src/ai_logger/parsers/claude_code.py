"""Parser for Claude Code JSONL transcripts."""

import json
from pathlib import Path

from ..models import ParsedTranscript, TranscriptMessage


def parse_claude_code_transcript(transcript_path: Path) -> ParsedTranscript:
    """Parse a Claude Code JSONL transcript file.

    Claude Code transcripts are JSONL files where each line contains:
    - type: "user", "assistant", "file-history-snapshot", etc.
    - message: Contains role and content
    - sessionId, uuid, parentUuid for threading

    Args:
        transcript_path: Path to the .jsonl transcript file

    Returns:
        ParsedTranscript with messages and raw text for summarization

    Raises:
        FileNotFoundError: If transcript file does not exist
        PermissionError: If transcript file cannot be read
    """
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    messages: list[TranscriptMessage] = []
    raw_parts: list[str] = []

    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            if entry_type not in ("user", "assistant"):
                continue

            message_data = entry.get("message", {})
            role = message_data.get("role", entry_type)
            content = _extract_content(message_data)

            if not content:
                continue

            messages.append(
                TranscriptMessage(
                    role=role,
                    content=content,
                    tool_use=_extract_tool_use(message_data),
                    tool_result=_extract_tool_result(message_data),
                )
            )

            # Build raw text for summarization
            prefix = "User: " if role == "user" else "Assistant: "
            raw_parts.append(f"{prefix}{content}")

    raw_text = "\n\n".join(raw_parts)
    token_estimate = len(raw_text) // 4  # Rough estimate: 4 chars per token

    return ParsedTranscript(
        messages=messages,
        raw_text=raw_text,
        token_estimate=token_estimate,
    )


def _extract_content(message_data: dict) -> str:
    """Extract text content from a message."""
    content = message_data.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        # Content can be a list of blocks (text, tool_use, thinking, etc.)
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    text_parts.append(f"[Tool: {tool_name}]")
            elif isinstance(block, str):
                text_parts.append(block)
        return " ".join(text_parts)

    return ""


def _extract_tool_use(message_data: dict) -> dict | None:
    """Extract tool use information if present."""
    content = message_data.get("content")
    if not isinstance(content, list):
        return None

    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return {
                "name": block.get("name"),
                "input": block.get("input"),
            }
    return None


def _extract_tool_result(message_data: dict) -> dict | None:
    """Extract tool result information if present."""
    content = message_data.get("content")
    if not isinstance(content, list):
        return None

    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            return {
                "tool_use_id": block.get("tool_use_id"),
                "content": block.get("content"),
            }
    return None
