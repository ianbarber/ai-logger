#!/bin/bash
# AI Logger hook script for Claude Code
# Called on session exit to log the session to Roam Research.
#
# Install: Add to ~/.claude/settings.json hooks.Stop

# Skip if inside a summarization job (prevents infinite recursion)
if [ -n "$AI_LOGGER_RUNNING" ]; then
    exit 0
fi

# Read JSON input from stdin
INPUT=$(cat)

# Skip if stop_hook_active is true (prevents hook chains)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# Extract fields from JSON
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Skip if no session ID or transcript
if [ -z "$SESSION_ID" ]; then
    exit 0
fi

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    exit 0
fi

# Run the logger in background to not block claude exit
ai-logger log \
    --source claude-code \
    --session-id "$SESSION_ID" \
    --transcript "$TRANSCRIPT_PATH" \
    --cwd "$CWD" \
    --machine "$(hostname)" \
    ${TMUX:+--tmux "$TMUX"} &

exit 0
