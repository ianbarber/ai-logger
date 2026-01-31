"""CLI entry point for ai-logger."""

from pathlib import Path
from typing import Optional

import click

from .models import AgentSource
from .pipeline import SessionSkipped


@click.group()
@click.version_option()
def main():
    """AI Session Logger - Log coding sessions to Roam Research."""
    pass


@main.command()
@click.option("--source", type=click.Choice(["claude-code", "codex"]), required=True)
@click.option("--session-id", required=True)
@click.option("--transcript", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--cwd", required=True)
@click.option("--machine", required=True)
@click.option("--tmux", default=None)
def log(
    source: str,
    session_id: str,
    transcript: Path,
    cwd: str,
    machine: str,
    tmux: Optional[str],
):
    """Log a completed session to Roam Research.

    This command is typically called by session hooks.
    """
    from .models import SessionEvent
    from .pipeline import process_session

    event = SessionEvent(
        source=AgentSource(source),
        session_id=session_id,
        transcript_path=str(transcript),
        cwd=cwd,
        machine=machine,
        tmux_session=tmux,
    )

    try:
        process_session(event)
        click.echo(f"Session {session_id} logged successfully")
    except SessionSkipped as e:
        # Session was skipped (no new content or trivial) - this is expected
        click.echo(f"Session {session_id} skipped: {e}")
    except Exception as e:
        # Queue for retry
        from .queue import enqueue_failed
        enqueue_failed(event, str(e))
        click.echo(f"Session queued for retry: {e}", err=True)


@main.command()
@click.option("--quiet", "-q", is_flag=True, help="Suppress output")
def retry(quiet: bool):
    """Process any failed jobs in the queue."""
    from .queue import get_pending_jobs, mark_completed, mark_failed
    from .pipeline import process_session

    jobs = get_pending_jobs()
    if not jobs and not quiet:
        click.echo("No pending jobs")
        return

    success = 0
    skipped = 0
    failed = 0
    for job_id, event in jobs:
        try:
            process_session(event)
            mark_completed(job_id)
            success += 1
        except SessionSkipped:
            # Skipped sessions are marked as completed (not failures)
            mark_completed(job_id)
            skipped += 1
        except Exception as e:
            mark_failed(job_id, str(e))
            failed += 1

    if not quiet:
        click.echo(f"Processed: {success} succeeded, {skipped} skipped, {failed} failed")


@main.command()
def status():
    """Show pending jobs in the queue."""
    from .queue import get_queue_status

    stats = get_queue_status()
    click.echo(f"Pending: {stats['pending']}")
    click.echo(f"Failed:  {stats['failed']}")
    click.echo(f"Total:   {stats['total']}")


if __name__ == "__main__":
    main()
