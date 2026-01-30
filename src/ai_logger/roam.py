"""Roam Research API client for publishing session logs."""

import secrets
import string
from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import get_settings
from .models import SessionEvent, SessionSummary


def _generate_uid() -> str:
    """Generate a Roam-style block UID (9 alphanumeric characters)."""
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(9))


class RoamError(Exception):
    """Error interacting with Roam Research API."""

    pass


class RetryableRoamError(Exception):
    """Roam error that should trigger a retry."""

    pass


def _get_daily_page_title() -> str:
    """Get today's daily note title in Roam format (Month DDth, YYYY).

    Uses local time since Roam daily notes are based on user's local date.
    """
    today = datetime.now()
    day = today.day
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return today.strftime(f"%B {day}{suffix}, %Y")


def _build_batch_actions(
    event: SessionEvent, summary: SessionSummary, daily_title: str
) -> list[dict[str, object]]:
    """Build batch actions to create parent block with nested children.

    Returns list of create-block actions for batch-actions API call.
    """
    timestamp = datetime.now().strftime("%H:%M")
    agent_ref = f"[[{event.source.value}]]"

    # Generate UID for parent block so children can reference it
    parent_uid = _generate_uid()

    actions = []

    # Parent block - main session header
    main_block = f"**{timestamp}** `{event.machine}` {agent_ref}"
    actions.append({
        "action": "create-block",
        "location": {
            "page-title": daily_title,
            "order": "last",
        },
        "block": {
            "uid": parent_uid,
            "string": main_block,
        },
    })

    # Child blocks - each as separate action with parent-uid
    children = []

    # Metadata
    children.append(f"project:: `{event.cwd}`")
    if event.tmux_session and event.tmux_session != "none":
        children.append(f"tmux:: `{event.tmux_session}`")

    # Summary
    children.append(summary.summary)

    # PRs
    for pr in summary.prs:
        pr_text = f"#PR [{pr.title or 'Pull Request'}]({pr.url})"
        if pr.action and pr.action != "created":
            pr_text += f" ({pr.action})"
        children.append(pr_text)

    # Services
    for svc in summary.services:
        children.append(f"#service `{svc.name}` {svc.action}")

    # Notable artifacts (limit to 3)
    for artifact in summary.artifacts[:3]:
        children.append(f"#artifact `{artifact.path}` - {artifact.description}")

    # Create child block actions
    for i, child_text in enumerate(children):
        actions.append({
            "action": "create-block",
            "location": {
                "parent-uid": parent_uid,
                "order": i,  # Maintain order
            },
            "block": {
                "string": child_text,
            },
        })

    return actions


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=10, max=300),
    retry=retry_if_exception_type(RetryableRoamError),
)
def publish_to_roam(event: SessionEvent, summary: SessionSummary) -> str:
    """Publish session summary to Roam Research daily note.

    Args:
        event: Session event with metadata
        summary: Summarized session information

    Returns:
        UID of the created block

    Raises:
        RoamError: If publishing fails permanently
        RetryableRoamError: If publishing fails but should be retried
    """
    settings = get_settings()

    daily_title = _get_daily_page_title()
    actions = _build_batch_actions(event, summary, daily_title)

    # Build the API request
    # Roam API: POST to /write endpoint with batch-actions
    url = f"https://api.roamresearch.com/api/graph/{settings.roam_graph_name}/write"
    headers = {
        "X-Authorization": f"Bearer {settings.roam_api_token}",
        "Content-Type": "application/json",
    }

    # Use batch-actions to create parent and all children atomically
    payload = {
        "action": "batch-actions",
        "actions": actions,
    }

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.post(url, headers=headers, json=payload)

            if response.status_code == 429:
                raise RetryableRoamError("Rate limited by Roam API")

            if response.status_code >= 500:
                raise RetryableRoamError(f"Roam server error: {response.status_code}")

            if response.status_code not in (200, 204):
                raise RoamError(
                    f"Roam API error: {response.status_code} - {response.text}"
                )

            # Handle empty response (success with no content)
            if not response.text.strip():
                return "success"

            result = response.json()
            return result.get("uid", "success")

    except httpx.TimeoutException:
        raise RetryableRoamError("Roam API timeout")
    except httpx.RequestError as e:
        raise RetryableRoamError(f"Network error: {e}")


def publish_simple_block(content: str, page_title: Optional[str] = None) -> str:
    """Publish a simple text block to Roam.

    Args:
        content: The block content
        page_title: Page title (defaults to today's daily note)

    Returns:
        UID of the created block
    """
    settings = get_settings()
    page_title = page_title or _get_daily_page_title()

    url = f"https://api.roamresearch.com/api/graph/{settings.roam_graph_name}/write"
    headers = {
        "X-Authorization": f"Bearer {settings.roam_api_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "action": "create-block",
        "location": {
            "page-title": page_title,
            "order": "last",
        },
        "block": {
            "string": content,
        },
    }

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            # Handle empty response (success with no content)
            if not response.text.strip():
                return "success"

            return response.json().get("uid", "unknown")
    except httpx.TimeoutException:
        raise RoamError("Roam API timeout")
    except httpx.RequestError as e:
        raise RoamError(f"Network error: {e}")
