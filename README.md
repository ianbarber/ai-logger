# ai-logger

Log AI coding sessions to Roam Research. Summarizes transcripts using Claude and publishes structured entries to your daily notes.

Built with [Claude Code](https://claude.ai/code).

## Installation

```bash
pip install -e .
```

## Configuration

Create `~/.config/ai-logger/.env`:

```
ROAM_GRAPH_NAME=your-graph-name
ROAM_API_TOKEN=your-roam-api-token
```

## Usage

### Manual logging

```bash
ai-logger log \
  --source claude-code \
  --session-id <session-id> \
  --transcript /path/to/transcript.jsonl \
  --cwd /path/to/project \
  --machine $(hostname)
```

### Claude Code hook (automatic)

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/scripts/claude-hook.sh"
          }
        ]
      }
    ]
  }
}
```

### Manual logging with `/note`

If you have the `/note` skill installed in Claude Code, you can manually log the current session by typing `/note` in the chat. This runs the same logging pipeline as the automatic hook.

To install the skill, create `~/.claude/skills/note/SKILL.md`:

```markdown
---
name: note
description: Log a summary of this session to Roam Research
allowed-tools: Bash, Read
---

Log the current session to Roam Research by running ai-logger.

Run this command:

ai-logger log \
    --source claude-code \
    --session-id "${CLAUDE_SESSION_ID}" \
    --transcript "${CLAUDE_TRANSCRIPT_PATH}" \
    --cwd "$(pwd)" \
    --machine "$(hostname)"

After running, confirm to the user that the session was logged (or report any errors).
```

### Retry failed jobs

```bash
ai-logger retry
ai-logger status
```

## How It Works

### Incremental Logging

The logger tracks state per session to avoid duplicate content:

- **Line tracking**: Remembers how many lines were processed in each session's transcript
- **Triviality check**: Uses Claude Haiku to quickly determine if new content is worth logging (skips sessions that are just browsing/reading files)
- **Context preservation**: When logging incrementally, includes a brief summary of previous work for context

State is stored in `~/.local/state/ai-logger/sessions/`.

### What Gets Logged

Each log entry in Roam includes:
- Timestamp and machine name
- Project path and tmux session (if applicable)
- AI-generated summary of the work done
- Any PRs created/updated
- Services started/deployed
- Notable artifacts created

## License

MIT
