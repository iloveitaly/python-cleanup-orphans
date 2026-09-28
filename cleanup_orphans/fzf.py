"""Interactive fzf-based process selection."""

import subprocess
import sys

from .scanner import Candidate


def select_with_fzf(candidates: list[Candidate]) -> list[int]:
    """Present candidates in fzf multi-select and return selected PIDs."""
    # column header shown as a fixed non-selectable line in fzf
    header = (
        f"{'PID':<7} | {'TYPE':<14} | {'REASON':<28} | {'AGE':<12} "
        f"| {'STARTED':<15} | {'CPU':<8} | DETAIL"
    )

    lines = [header]
    for c in candidates:
        line = (
            f"{c.pid:<7} | {c.category:<14} | {c.reason:<28} | {c.age:<12} "
            f"| {c.started:<15} | {c.cpu:<8} | {c.detail}"
        )
        lines.append(line)

    fzf_input = "\n".join(lines)
    try:
        proc = subprocess.Popen(
            [
                "fzf",
                "-m",
                "--layout=reverse",
                "--no-sort",
                # first line of input is the column header
                "--header-lines=1",
                "--header=TAB: select/deselect | Ctrl-A: toggle all | ENTER: kill selected | ESC: quit",
                "--bind=ctrl-a:toggle-all",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        stdout, _ = proc.communicate(input=fzf_input)

        if proc.returncode != 0:
            return []

        selected_pids = []
        for line in stdout.strip().splitlines():
            pid_str = line.split("|")[0].strip()
            if pid_str.isdigit():
                selected_pids.append(int(pid_str))

        return selected_pids
    except FileNotFoundError:
        print("Error: fzf is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)
