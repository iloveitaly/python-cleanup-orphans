"""CLI entrypoint for cleanup-orphans."""

import click
from structlog_config import configure_logger

from .fzf import select_with_fzf
from .killer import kill_pids
from .scanner import Candidate, find_candidates
from .version import __version__

log = configure_logger()


def _print_table(candidates: list[Candidate]) -> None:
    header = f"{'PID':<7} {'PPID':<7} {'CATEGORY':<14} {'REASON':<28} {'AGE':<14} {'STARTED':<15} {'CPU':<9} {'DETAIL'}"
    click.echo(header)
    click.echo("-" * 135)

    for c in candidates:
        click.echo(
            f"{c.pid:<7} {c.ppid:<7} {c.category:<14} {c.reason:<28} {c.age:<14} {c.started:<15} {c.cpu:<9} {c.detail}"
        )

    click.echo("-" * 135)
    click.echo(f"Total candidates: {len(candidates)}")


@click.command()
@click.version_option(version=__version__)
@click.option(
    "--list",
    "list_only",
    is_flag=True,
    help="List candidates in table format (dry-run)",
)
@click.option(
    "--kill-all", is_flag=True, help="Kill all candidates with confirmation prompt"
)
def cli(list_only: bool, kill_all: bool) -> None:
    """Detect and safely terminate orphaned AI agent processes.

    Default mode opens an interactive fzf selector.
    """
    candidates = find_candidates()
    if not candidates:
        click.echo("No orphaned or rogue AI processes found.")
        return

    if list_only:
        _print_table(candidates)
        return

    if kill_all:
        _print_table(candidates)
        if click.confirm(f"\nKill all {len(candidates)} candidates?", default=False):
            kill_pids([c.pid for c in candidates])
        else:
            click.echo("Aborted.")
        return

    # default: interactive fzf selection
    selected_pids = select_with_fzf(candidates)
    if not selected_pids:
        click.echo("Aborted. No processes selected.")
        return

    if click.confirm(
        f"\nKill {len(selected_pids)} selected process(es)?", default=False
    ):
        kill_pids(selected_pids)
    else:
        click.echo("Aborted.")
