"""Process info helpers: cwd lookup, time/cpu parsing, and formatting."""

import contextlib
import ctypes
import ctypes.util
import os
import subprocess


def get_current_process_tree() -> set[int]:
    """Return PIDs in our own process lineage so we never kill ourselves."""
    pids = set()
    pid = os.getpid()

    while pid > 1:
        pids.add(pid)
        try:
            out = (
                subprocess.check_output(["ps", "-o", "ppid=", "-p", str(pid)])
                .decode()
                .strip()
            )
            pid = int(out)
        except (subprocess.SubprocessError, ValueError):
            break

    return pids


def parse_cpu_minutes(cputime: str) -> float:
    """Parse BSD ps cputime (minutes:seconds.hundredths) into float minutes."""
    parts = cputime.split(":")

    if len(parts) == 2:
        return float(parts[0]) + float(parts[1]) / 60.0
    elif len(parts) == 3:
        # hours:minutes:seconds
        return float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0

    return 0.0


def parse_elapsed_seconds(etime: str) -> int:
    """Convert BSD etime ([[dd-]hh:]mm:ss) into integer seconds."""
    days, hours, mins, secs = 0, 0, 0, 0

    if "-" in etime:
        day_part, rest = etime.split("-", 1)
        days = int(day_part)
        time_parts = rest.split(":")
    else:
        time_parts = etime.split(":")

    if len(time_parts) == 3:
        hours, mins, secs = map(int, time_parts)
    elif len(time_parts) == 2:
        mins, secs = map(int, time_parts)
    elif len(time_parts) == 1:
        secs = int(time_parts[0])

    return days * 86_400 + hours * 3_600 + mins * 60 + secs


def format_elapsed(etime: str) -> str:
    """Convert BSD etime ([[dd-]hh:]mm:ss) into a human-readable age string."""
    days, hours, mins, secs = 0, 0, 0, 0

    if "-" in etime:
        day_part, rest = etime.split("-", 1)
        days = int(day_part)
        time_parts = rest.split(":")
    else:
        time_parts = etime.split(":")

    if len(time_parts) == 3:
        hours, mins, secs = map(int, time_parts)
    elif len(time_parts) == 2:
        mins, secs = map(int, time_parts)
    elif len(time_parts) == 1:
        secs = int(time_parts[0])

    if days > 0:
        return f"{days}d {hours}h ago"
    if hours > 0:
        return f"{hours}h {mins}m ago"
    if mins > 0:
        return f"{mins}m ago"
    return f"{secs}s ago"


def format_cpu(cputime: str) -> str:
    """Convert BSD ps cputime into human-readable form."""
    parts = cputime.split(":")

    if len(parts) == 2:
        m = int(parts[0])
        s = float(parts[1])
        if m >= 60:
            return f"{m // 60}h {m % 60}m"
        if m > 0:
            return f"{m}m {int(s)}s"
        return f"{s:.1f}s"
    elif len(parts) == 3:
        h = int(parts[0])
        m = int(parts[1])
        return f"{h}h {m}m"

    return f"{float(parts[0]):.1f}s"


# C-level libproc wrapper for fast process cwd retrieval on macOS
_libproc = None
with contextlib.suppress(OSError):
    _libproc_path = ctypes.util.find_library("proc")
    if _libproc_path:
        _libproc = ctypes.CDLL(_libproc_path)
        _libproc.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        _libproc.proc_pidinfo.restype = ctypes.c_int


def get_process_cwd(pid: int) -> str:
    """Query current working directory using macOS libproc (PROC_PIDVNODEPATHINFO = 9)."""
    if not _libproc:
        return ""

    with contextlib.suppress(OSError, ValueError):
        buf = ctypes.create_string_buffer(2_352)
        # flavor 9 = PROC_PIDVNODEPATHINFO
        ret = _libproc.proc_pidinfo(pid, 9, 0, buf, ctypes.sizeof(buf))
        if ret <= 0:
            return ""

        # offset 152 is char vip_path[1024] inside pvi_cdir
        path_bytes = buf.raw[152 : 152 + 1_024]
        null_idx = path_bytes.find(b"\x00")
        if null_idx != -1:
            path_bytes = path_bytes[:null_idx]

        path_str = path_bytes.decode("utf-8", errors="replace").strip()
        if path_str:
            return path_str.replace(os.path.expanduser("~"), "~")

    return ""
