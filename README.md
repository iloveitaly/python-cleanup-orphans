[![Release Notes](https://img.shields.io/github/release/iloveitaly/python-cleanup-orphans)](https://github.com/iloveitaly/python-cleanup-orphans/releases)
[![Downloads](https://static.pepy.tech/badge/python-cleanup-orphans/month)](https://pepy.tech/project/python-cleanup-orphans)
![GitHub CI Status](https://github.com/iloveitaly/python-cleanup-orphans/actions/workflows/build_and_publish.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Clean Up Orphaned AI Agent Processes

I run AI coding tools all day—Cursor, agy, Claude, Codex—and they inevitably leave behind orphaned background workers, zombie MCP servers, and suspended terminal sessions reparented to launchd that chew through RAM and CPU. This CLI scans for abandoned agent processes, lays them out in an interactive fzf interface, and cleanly shuts them down along with their entire descendant process tree.

## Installation

```bash
uv tool install python-cleanup-orphans
```

Or add to an existing project:

```bash
uv add python-cleanup-orphans
```

## Usage

Launch interactive multi-select via `fzf`:

```bash
cleanup-orphans
```

Print candidates in a dry-run table:

```bash
cleanup-orphans --list
```

Terminate all identified candidates after confirmation:

```bash
cleanup-orphans --kill-all
```

## Features

- Scans for reparented Cursor agent workers (PPID 1)
- Flags suspended or stopped agent sessions (STAT T)
- Detects runaway agent sessions exceeding CPU thresholds
- Finds detached headless Claude CLI streaming processes
- Identifies orphaned OpenAI Codex CLI instances
- Recursively tracks and terminates child MCP servers, language servers, and watchdogs
- Graceful termination escalating from SIGTERM to SIGKILL
- Interactive terminal UI using `fzf` with a fixed column header row

## Comparison

Existing utilities fall into two camps: non-interactive batch daemons targeted at specific runtimes (`TheStack-ai/zclean`, `kojott/claude-gc`), or general-purpose process killers (`fkill`, shell wrappers) that lack process-lineage and AI-tool context.

`cleanup-orphans` combines AI ecosystem detection with interactive triage:

| Feature | `zclean` / `claude-gc` | `fkill` / `fzf` snippets | `cleanup-orphans` |
|---|---|---|---|
| Targets AI agent ecosystem | Yes (MCP, Claude) | No (all system procs) | Yes (Cursor workers, agy, Claude, Codex, MCP trees) |
| Interactive TUI triage | No (batch / cron only) | Yes (`fkill` / `fzf`) | Yes (`fzf` multi-select with `Ctrl-A` and confirmation) |
| Sorting | Unsorted / Name | Fuzzy search rank | Oldest-first by elapsed wall-clock time |
| Descendant cascade reaping | Basic | No | Full tree traversal (reaps child MCPs and watchdogs) |
| Working directory context | No | No | Yes (macOS `libproc` extraction of exact repo/worktree) |
| Job-control suspensions (`STAT T`) | No | No | Yes (identifies backgrounded `Ctrl-Z` sessions) |
| Human-readable metrics | Raw memory | Raw PID / Name | Formatted age (`15d 1h ago`) and CPU (`3h 18m`) |

## [MIT License](LICENSE.md)

---

*This project was created from [iloveitaly/python-package-template](https://github.com/iloveitaly/python-package-template)*