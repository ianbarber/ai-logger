#!/bin/bash
# AI Logger hook script for Claude Code
# Called on session exit to log the session to Roam Research.
#
# Guards:
# 1. AI_LOGGER_RUNNING - prevents recursion from summarizer
# 2. stop_hook_active - prevents hook chains
#
# Note: Cooldown/incremental logic is now handled in Python pipeline
#
# Install: Add to ~/.claude/settings.json hooks.Stop

# Guard: Skip if inside a summarization job
if [ -n "$AI_LOGGER_RUNNING" ]; then
    exit 0
fi

# Read JSON input from stdin
INPUT=$(cat)

# Guard: Skip if stop_hook_active is true
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# Extract fields from JSON
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Guard: Skip if no session ID or transcript
if [ -z "$SESSION_ID" ]; then
    exit 0
fi

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    exit 0
fi

# Get tmux session name if running inside tmux
TMUX_SESSION=""
if [ -n "$TMUX" ]; then
    TMUX_SESSION=$(tmux display-message -p '#S' 2>/dev/null)
fi

# Run the logger in background
ai-logger log \
    --source claude-code \
    --session-id "$SESSION_ID" \
    --transcript "$TRANSCRIPT_PATH" \
    --cwd "$CWD" \
    --machine "$(hostname)" \
    ${TMUX_SESSION:+--tmux "$TMUX_SESSION"} &

exit 0
