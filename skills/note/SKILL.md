---
name: note
description: Log a summary of this session to Roam Research
allowed-tools: Bash, Read, Glob
---

Log the current session to Roam Research by running ai-logger.

The session ID is provided in the command context above (look for `session-id` in the command-message).

To find the transcript path, the pattern is:
`~/.claude/projects/{project-path-with-slashes-replaced-by-dashes}/{session-id}.jsonl`

For example, if cwd is `/home/user/Projects/myapp` and session ID is `abc-123`, the transcript is at:
`~/.claude/projects/-home-user-Projects-myapp/abc-123.jsonl`

Run ai-logger with the discovered values:

```bash
ai-logger log \
    --source claude-code \
    --session-id "<session-id-from-context>" \
    --transcript "<computed-transcript-path>" \
    --cwd "$(pwd)" \
    --machine "$(hostname)"
```

After running, confirm to the user that the session was logged (or report any errors).
