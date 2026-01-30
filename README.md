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

See `scripts/` for example hook scripts.

### Retry failed jobs

```bash
ai-logger retry
ai-logger status
```

## License

MIT
