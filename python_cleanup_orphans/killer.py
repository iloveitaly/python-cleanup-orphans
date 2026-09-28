"""Process termination with SIGTERM -> SIGKILL escalation."""

import os
import signal
import subprocess
import time

import structlog

log = structlog.get_logger()


def _expand_descendants(pids: list[int]) -> list[int]:
    """Find all recursive child processes so no orphans are left behind."""
    all_pids = set(pids)
    out = subprocess.check_output(["ps", "-axo", "pid,ppid"]).decode("utf-8")

    pairs: list[tuple[int, int]] = []
    for line in out.strip().splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            pairs.append((int(parts[0]), int(parts[1])))

    added = True
    while added:
        added = False
        for pid, ppid in pairs:
            if ppid in all_pids and pid not in all_pids:
                all_pids.add(pid)
                added = True

    return sorted(all_pids)


def kill_pids(pids: list[int]) -> None:
    """Send SIGTERM to pids (plus descendants), escalating to SIGKILL after 1s."""
    if not pids:
        return

    targets = _expand_descendants(pids)
    if len(targets) > len(pids):
        extra = len(targets) - len(pids)
        log.info(
            "expanding targets", selected=len(pids), children=extra, total=len(targets)
        )

    log.info("sending SIGTERM", pids=targets)
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            log.warning("permission denied", pid=pid)

    time.sleep(1.0)

    # check for survivors and escalate
    still_alive = []
    for pid in targets:
        try:
            os.kill(pid, 0)
            still_alive.append(pid)
        except OSError:
            pass

    if still_alive:
        log.info("escalating to SIGKILL", pids=still_alive)
        for pid in still_alive:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    log.info("kill complete", pids=targets)
