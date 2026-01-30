#!/bin/bash
# Manually log a Claude Code session to Roam Research
# Usage: log-session-now.sh <session_id> <cwd>

set -e

SESSION_ID="$1"
CWD="$2"

if [ -z "$SESSION_ID" ] || [ -z "$CWD" ]; then
    echo "Usage: log-session-now.sh <session_id> <cwd>" >&2
    exit 1
fi

# Find the transcript file
PROJECT_HASH=$(echo "$CWD" | sed 's|^/||' | sed 's|/|-|g')
TRANSCRIPT_PATH="$HOME/.claude/projects/-${PROJECT_HASH}/${SESSION_ID}.jsonl"

if [ ! -f "$TRANSCRIPT_PATH" ]; then
    TRANSCRIPT_PATH="$HOME/.claude/projects/${PROJECT_HASH}/${SESSION_ID}.jsonl"
fi

if [ ! -f "$TRANSCRIPT_PATH" ]; then
    TRANSCRIPT_PATH=$(find ~/.claude/projects -name "${SESSION_ID}.jsonl" 2>/dev/null | head -1)
fi

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    echo "Error: Could not find transcript for session ${SESSION_ID}" >&2
    exit 1
fi

echo "Found transcript: $TRANSCRIPT_PATH"

ai-logger log \
    --source claude-code \
    --session-id "$SESSION_ID" \
    --transcript "$TRANSCRIPT_PATH" \
    --cwd "$CWD" \
    --machine "$(hostname)" \
    --tmux "${TMUX_PANE:-none}"

echo "Session logged to Roam successfully"
