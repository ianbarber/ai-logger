"""Data models for session logging."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class AgentSource(str, Enum):
    """Supported AI coding agents."""

    CLAUDE_CODE = "claude-code"
    CODEX = "codex"


class SessionEvent(BaseModel):
    """Event received from a session hook."""

    source: AgentSource
    session_id: str
    transcript_path: str
    cwd: str
    machine: str
    tmux_session: Optional[str] = None
    timestamp: datetime = Field(default_factory=_utc_now)


class PRInfo(BaseModel):
    """Information about a pull request."""

    url: str
    title: str
    action: str  # created, updated, reviewed


class ServiceInfo(BaseModel):
    """Information about a service action."""

    name: str
    action: str  # started, deployed, stopped


class ArtifactInfo(BaseModel):
    """Information about a created artifact."""

    type: str  # file, config, script
    path: str
    description: str


class SessionSummary(BaseModel):
    """Summarized session information."""

    summary: str
    prs: list[PRInfo] = Field(default_factory=list)
    services: list[ServiceInfo] = Field(default_factory=list)
    artifacts: list[ArtifactInfo] = Field(default_factory=list)


class TranscriptMessage(BaseModel):
    """A single message from a transcript."""

    role: str  # user, assistant, system
    content: str
    tool_use: Optional[dict[str, object]] = None
    tool_result: Optional[dict[str, object]] = None


class ParsedTranscript(BaseModel):
    """Parsed transcript ready for summarization."""

    messages: list[TranscriptMessage]
    raw_text: str  # For sending to Claude
    token_estimate: int = 0
