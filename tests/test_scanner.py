"""Tests for orphan process candidate detection."""

from python_cleanup_orphans.scanner import (
    Candidate,
    RawProcess,
    _check_agy,
    _check_claude_stream,
    _check_codex,
    _check_cursor_worker,
    _collect_descendants,
)


def _make_proc(
    pid: int = 100,
    ppid: int = 1,
    stat: str = "S",
    etime: str = "10:00",
    cputime: str = "0:10.00",
    cmd: str = "",
) -> RawProcess:
    return RawProcess(
        pid=pid,
        ppid=ppid,
        stat=stat,
        etime=etime,
        cputime=cputime,
        started="Sep 26 11:44",
        cmd=cmd,
    )


class TestCheckCursorWorker:
    def test_matches_orphaned_worker(self) -> None:
        proc = _make_proc(
            pid=1900,
            ppid=1,
            cmd="cursor-agent ... worker start --worker-dir /tmp/repo",
        )
        candidate = _check_cursor_worker(proc)
        assert candidate is not None
        assert candidate.category == "cursor-agent"
        assert candidate.reason == "Reparented to launchd (PPID 1)"

    def test_ignores_non_orphaned_worker(self) -> None:
        proc = _make_proc(
            pid=1900,
            ppid=500,
            cmd="cursor-agent worker start",
        )
        assert _check_cursor_worker(proc) is None

    def test_ignores_unrelated_process(self) -> None:
        proc = _make_proc(pid=1900, ppid=1, cmd="some-other-daemon")
        assert _check_cursor_worker(proc) is None


class TestCheckAgy:
    def test_matches_ppid_1_orphan(self) -> None:
        proc = _make_proc(pid=200, ppid=1, cmd="agy --continue")
        candidate = _check_agy(proc)
        assert candidate is not None
        assert candidate.category == "agy"
        assert candidate.reason == "Reparented to launchd (PPID 1)"

    def test_matches_suspended(self) -> None:
        proc = _make_proc(pid=201, ppid=500, stat="T", cmd="agy")
        candidate = _check_agy(proc)
        assert candidate is not None
        assert candidate.category == "agy"
        assert "Suspended" in candidate.reason

    def test_matches_high_cpu(self) -> None:
        proc = _make_proc(pid=202, ppid=500, cputime="500:00.00", cmd="agy")
        candidate = _check_agy(proc)
        assert candidate is not None
        assert candidate.reason == "High CPU usage"

    def test_ignores_normal_running_agy(self) -> None:
        proc = _make_proc(pid=203, ppid=500, cputime="10:00.00", cmd="agy")
        assert _check_agy(proc) is None


class TestCheckCodex:
    def test_matches_reparented_codex(self) -> None:
        proc = _make_proc(pid=300, ppid=1, cmd="codex-code-mode-host")
        candidate = _check_codex(proc)
        assert candidate is not None
        assert candidate.category == "codex"
        assert candidate.reason == "Reparented to launchd (PPID 1)"

    def test_matches_suspended_codex(self) -> None:
        proc = _make_proc(pid=301, ppid=500, stat="T", cmd="codex")
        candidate = _check_codex(proc)
        assert candidate is not None
        assert candidate.category == "codex"

    def test_ignores_active_child_codex(self) -> None:
        proc = _make_proc(pid=302, ppid=500, cputime="0:05.00", cmd="codex")
        assert _check_codex(proc) is None


class TestCheckClaudeStream:
    def test_matches_stream_json(self) -> None:
        proc = _make_proc(pid=400, ppid=500, cmd="claude --output-format stream-json")
        candidate = _check_claude_stream(proc)
        assert candidate is not None
        assert candidate.category == "claude"

    def test_ignores_regular_claude(self) -> None:
        proc = _make_proc(pid=401, ppid=500, cmd="claude chat")
        assert _check_claude_stream(proc) is None


class TestCollectDescendants:
    def test_resolves_parent_and_grandparent_labels(self) -> None:
        parent = Candidate(
            pid=1000,
            ppid=1,
            category="cursor-agent",
            reason="Reparented to launchd (PPID 1)",
            cpu="1.0s",
            age="10m ago",
            elapsed_seconds=600,
            started="Sep 26 11:44",
            cwd="",
            detail="parent",
        )
        child_proc = _make_proc(pid=1001, ppid=1000, cmd="mcp-server")
        grandchild_proc = _make_proc(pid=1002, ppid=1001, cmd="node watcher.js")

        pids = {1000}
        candidates_by_pid = {1000: parent}
        descendants = _collect_descendants(
            pids,
            candidates_by_pid,
            [child_proc, grandchild_proc],
        )

        assert len(descendants) == 2
        assert descendants[0].pid == 1001
        assert descendants[0].reason == "Child of cursor-agent (1000)"
        assert descendants[1].pid == 1002
        assert descendants[1].reason == "Child of child (1001)"
