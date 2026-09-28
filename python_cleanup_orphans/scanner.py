"""Scan running processes to find orphaned AI agent candidates."""

import os
import subprocess

from pydantic import BaseModel

from .process import (
    format_cpu,
    format_elapsed,
    get_current_process_tree,
    get_process_cwd,
    parse_cpu_minutes,
    parse_elapsed_seconds,
)


class Candidate(BaseModel):
    pid: int
    ppid: int
    category: str
    reason: str
    cpu: str
    age: str
    elapsed_seconds: int
    started: str
    cwd: str
    detail: str


class RawProcess(BaseModel):
    pid: int
    ppid: int
    stat: str
    etime: str
    cputime: str
    started: str
    cmd: str


def _parse_process_list() -> list[RawProcess]:
    """Parse `ps` output into structured process records."""
    out = subprocess.check_output(
        ["ps", "-axo", "pid,ppid,stat,etime,cputime,lstart,command"]
    ).decode("utf-8")

    processes: list[RawProcess] = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 10)
        if len(parts) < 11:
            continue

        pid_s, ppid_s, stat, etime, cputime, _day, month, date, time_str, _year, cmd = (
            parts
        )
        processes.append(
            RawProcess(
                pid=int(pid_s),
                ppid=int(ppid_s),
                stat=stat,
                etime=etime,
                cputime=cputime,
                started=f"{month} {date} {time_str[:5]}",
                cmd=cmd,
            )
        )

    return processes


def _build_candidate(
    proc: RawProcess, category: str, reason: str, detail: str, cwd: str
) -> Candidate:
    return Candidate(
        pid=proc.pid,
        ppid=proc.ppid,
        category=category,
        reason=reason,
        cpu=format_cpu(proc.cputime),
        age=format_elapsed(proc.etime),
        elapsed_seconds=parse_elapsed_seconds(proc.etime),
        started=proc.started,
        cwd=cwd,
        detail=detail,
    )


def _check_cursor_worker(proc: RawProcess) -> Candidate | None:
    """Cursor agent workers reparented to launchd (PPID 1) are orphans."""
    if (
        "cursor-agent" not in proc.cmd
        or "worker start" not in proc.cmd
        or proc.ppid != 1
    ):
        return None

    ws = ""
    if "--worker-dir" in proc.cmd:
        ws = proc.cmd.split("--worker-dir")[1].strip().split()[0]
        ws = ws.replace(os.path.expanduser("~"), "~")

    cwd = get_process_cwd(proc.pid)
    return _build_candidate(
        proc, "cursor-agent", "Reparented to launchd (PPID 1)", ws or cwd, cwd or ws
    )


def _check_agy(proc: RawProcess) -> Candidate | None:
    """AGY sessions that are orphaned, suspended, or consuming excessive CPU."""
    is_agy = "agy " in proc.cmd or proc.cmd.endswith("agy")
    if not is_agy:
        return None

    cwd = get_process_cwd(proc.pid)
    detail = f"[{cwd}] {proc.cmd[:50]}" if cwd else proc.cmd[:60]

    if proc.ppid == 1:
        return _build_candidate(
            proc, "agy", "Reparented to launchd (PPID 1)", detail, cwd
        )
    if "T" in proc.stat:
        return _build_candidate(
            proc, "agy", f"Suspended (STAT {proc.stat})", detail, cwd
        )
    # 8 hours of CPU is excessive for any single agent session
    if parse_cpu_minutes(proc.cputime) > 480:
        return _build_candidate(proc, "agy", "High CPU usage", detail, cwd)

    return None


def _is_codex_process(cmd: str) -> bool:
    return "codex " in cmd or cmd.endswith("codex") or "codex-code-mode-host" in cmd


def _check_codex(proc: RawProcess) -> Candidate | None:
    """Codex CLI processes that are orphaned, suspended, or consuming excessive CPU."""
    if not _is_codex_process(proc.cmd):
        return None

    cwd = get_process_cwd(proc.pid)
    detail = f"[{cwd}] {proc.cmd[:50]}" if cwd else proc.cmd[:60]

    if proc.ppid == 1:
        return _build_candidate(
            proc, "codex", "Reparented to launchd (PPID 1)", detail, cwd
        )
    if "T" in proc.stat:
        return _build_candidate(
            proc, "codex", f"Suspended (STAT {proc.stat})", detail, cwd
        )
    if parse_cpu_minutes(proc.cputime) > 480:
        return _build_candidate(proc, "codex", "High CPU usage", detail, cwd)

    return None


def _check_claude_stream(proc: RawProcess) -> Candidate | None:
    """Detached headless Claude stream-json processes."""
    if "claude " not in proc.cmd or "--output-format stream-json" not in proc.cmd:
        return None

    cwd = get_process_cwd(proc.pid)
    detail = f"[{cwd}] {proc.cmd[:50]}" if (cwd and cwd != "/") else proc.cmd[:60]
    return _build_candidate(proc, "claude", "Detached headless stream", detail, cwd)


# ordered list of detection heuristics
_CHECKERS = [
    _check_cursor_worker,
    _check_codex,
    _check_agy,
    _check_claude_stream,
]


def _collect_descendants(
    candidate_pids: set[int],
    candidates_by_pid: dict[int, Candidate],
    all_processes: list[RawProcess],
) -> list[Candidate]:
    """Recursively find child processes of candidates (e.g. MCP servers spawned by cursor workers)."""
    descendants: list[Candidate] = []
    added = True

    while added:
        added = False
        for proc in all_processes:
            if proc.ppid not in candidate_pids or proc.pid in candidate_pids:
                continue

            parent = candidates_by_pid.get(proc.ppid)
            parent_label = parent.category if parent else "unknown"
            reason = f"Child of {parent_label} ({proc.ppid})"

            cwd = get_process_cwd(proc.pid)
            detail = f"[{cwd}] {proc.cmd[:45]}" if cwd else proc.cmd[:60]
            child = _build_candidate(proc, "child", reason, detail, cwd)
            descendants.append(child)
            # register so grandchildren can resolve their parent too
            candidates_by_pid[proc.pid] = child
            candidate_pids.add(proc.pid)
            added = True

    return descendants


def find_candidates() -> list[Candidate]:
    """Scan all running processes and return orphaned AI agent candidates, oldest first."""
    current_tree = get_current_process_tree()
    all_processes = _parse_process_list()

    candidates: list[Candidate] = []
    for proc in all_processes:
        if proc.pid in current_tree:
            continue

        for checker in _CHECKERS:
            candidate = checker(proc)
            if candidate:
                candidates.append(candidate)
                # only match the first applicable category
                break

    # collect child processes of all matched candidates
    candidate_pids = {c.pid for c in candidates}
    candidates_by_pid = {c.pid: c for c in candidates}
    descendants = _collect_descendants(candidate_pids, candidates_by_pid, all_processes)
    candidates.extend(descendants)

    # oldest first
    candidates.sort(key=lambda c: c.elapsed_seconds, reverse=True)
    return candidates
