"""Render the task and bug boards from the files themselves (`BOT-163`).

Every task and bug file carries its own one-line board entry, its `**Board:**`
field. This script reads the files and writes the count tables and the lists;
no pull request edits a shared list, so two pull requests never touch the same
lines. Entries written by hand before the boards were generated are frozen in
`Tasks/history/` and are linked, not repeated.

Usage:
    python3 scripts/render_board.py          # print the board
    python3 scripts/render_board.py --write  # write Tasks/BOARD.md (not tracked)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Run bare, nothing puts the checkout's parent on the path; the sibling module is
# imported by its package name, the one the guards and mypy resolve, as in
# `measure_process.py`.
sys.path.insert(
    0,
    str(
        next(
            p
            for p in Path(__file__).resolve().parents
            if (p / "pyproject.toml").is_file()
        ).parent
    ),
)

from Sagittarius_Elite_Warrior.scripts.render_task_counts import (
    POOLS,
    count_tasks,
    render_rows,
    repo_root,
)

BOARD_FILE = "BOARD.md"
HISTORY_DIR = "history"
TASK_POOLS = tuple(pool for pool, _ in POOLS)
BUG_POOLS = ("bug_report/incomplete", "bug_report/completed")
#: Pools whose files may still be listed only by the frozen history: they no
#: longer change state. An open file always carries its own `**Board:**` line.
CLOSED_POOLS = ("completed", "cancelled", "bug_report/completed")
#: Epic children report on the roadmap too; their epic's README stays their board.
EPIC_CHILD_GLOB = "epics/EPIC-*/completed/*.md"

_ID = re.compile(r"^([A-Z]+-\d+[A-Z]?\d*)(?:_|\.md$)")
#: An id where it is cited, in prose or inside a file name (`BOT-042C_series.md`).
_MENTION = re.compile(r"(?<![A-Za-z0-9])([A-Z]+-\d+[A-Z]?\d*)")
_HEADING = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_DATE = re.compile(r"\((\d{4}-\d{2}-\d{2})")


def _field(text: str, name: str) -> str:
    """The value of a `**Name:**` header field, bulleted or not; blank if absent."""
    match = re.search(rf"^(?:- )?\*\*{name}:\*\*\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


@dataclass(frozen=True)
class Entry:
    """One task or bug file, as its board shows it."""

    entry_id: str
    link: str
    title: str
    status: str
    board: str
    priority: str
    severity: str

    @property
    def date(self) -> str:
        """The date the status names (done, fixed, cancelled), or blank."""
        match = _DATE.search(self.status)
        return match.group(1) if match else ""


def _title(heading: str, entry_id: str) -> str:
    """The heading without its leading id: `BOT-1 — Outcome` reads `Outcome`."""
    prefix = f"{entry_id} — "
    return heading.strip().removeprefix(prefix) or entry_id


def read_entry(path: Path, tasks_dir: Path) -> Entry | None:
    """The entry a file declares, or None for a file that is not a task or bug."""
    match = _ID.match(path.name)
    if match is None:
        return None
    text = path.read_text("utf-8")
    heading = _HEADING.search(text)
    return Entry(
        entry_id=match.group(1),
        link=path.relative_to(tasks_dir).as_posix(),
        title=_title(heading.group(1) if heading else "", match.group(1)),
        status=_field(text, "Status"),
        board=_field(text, "Board"),
        priority=_field(text, "Priority"),
        severity=_field(text, "Severity"),
    )


def read_pool(tasks_dir: Path, pattern: str) -> list[Entry]:
    """Every entry under one pool directory (or glob), by id."""
    paths = sorted(tasks_dir.glob(pattern if "*" in pattern else f"{pattern}/*.md"))
    entries = (read_entry(path, tasks_dir) for path in paths)
    return [entry for entry in entries if entry is not None]


def history_ids(tasks_dir: Path) -> set[str]:
    """Every id the frozen, hand-written boards in `Tasks/history/` mention."""
    found: set[str] = set()
    for path in sorted((tasks_dir / HISTORY_DIR).glob("*.md")):
        found.update(_MENTION.findall(path.read_text("utf-8")))
    return found


def missing_board_lines(tasks_dir: Path) -> list[str]:
    """Files no board shows: no `**Board:**` field, and not a closed file the
    frozen history already lists."""
    frozen = history_ids(tasks_dir)
    missing = []
    for pool in (*TASK_POOLS, *BUG_POOLS):
        for entry in read_pool(tasks_dir, pool):
            listed = pool in CLOSED_POOLS and entry.entry_id in frozen
            if not entry.board and not listed:
                missing.append(entry.link)
    return missing


def _newest_first(entries: list[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda entry: (entry.date, entry.entry_id), reverse=True)


def _items(entries: list[Entry]) -> list[str]:
    """One bullet per entry that has a board line; history covers the rest."""
    rows = []
    for entry in entries:
        if entry.board:
            stamp = f" — {entry.date}" if entry.date else ""
            rows.append(
                f"- **[`{entry.entry_id}`]({entry.link})** ({entry.title}){stamp}: {entry.board}"
            )
    return rows or ["_None._"]


def _table(head: str, rows: list[str]) -> list[str]:
    columns = head.count("|") - 1
    return [head, "|" + " :--- |" * columns, *rows] if rows else ["_None._"]


def _section(title: str, body: list[str]) -> list[str]:
    return [f"## {title}", "", *body, ""]


def _open_bug_rows(bugs: list[Entry]) -> list[str]:
    return [
        f"| **[{bug.entry_id}]({bug.link})** | {bug.title} | {bug.severity} | {bug.board} |"
        for bug in bugs
    ]


def _backlog_rows(tasks: list[Entry]) -> list[str]:
    ordered = sorted(tasks, key=lambda task: (task.priority or "P9", task.entry_id))
    return [
        f"| {task.priority or '—'} | **[{task.entry_id}]({task.link})** | {task.title} | {task.board} |"
        for task in ordered
    ]


def _history_links(tasks_dir: Path) -> list[str]:
    paths = sorted((tasks_dir / HISTORY_DIR).glob("*.md"))
    return [f"- [{path.stem}]({HISTORY_DIR}/{path.name})" for path in paths]


def render_board(tasks_dir: Path) -> str:
    """The whole board as Markdown, newest entries first."""
    pools = {pool: read_pool(tasks_dir, pool) for pool in (*TASK_POOLS, *BUG_POOLS)}
    completed = pools["completed"] + read_pool(tasks_dir, EPIC_CHILD_GLOB)
    open_bugs, fixed_bugs = pools[BUG_POOLS[0]], pools[BUG_POOLS[1]]
    count_table = ["| Status | Tasks | Share |", "| :--- | :---: | :---: |"]
    lines = [
        "# Task and bug board",
        "",
        "> Generated by `python3 scripts/render_board.py` from each file's `**Board:**` field.",
        "> Do not edit it: change the task or bug file.",
        "",
        *_section("📊 Tasks", [*count_table, *render_rows(count_tasks(tasks_dir))]),
        *_section(
            f"🐞 Bugs: {len(open_bugs)} open, {len(fixed_bugs)} fixed",
            _table("| ID | Title | Severity | Board |", _open_bug_rows(open_bugs)),
        ),
        *_section("🟡 In progress", _items(pools["in_progress"])),
        *_section(
            "🔴 Backlog",
            _table(
                "| Priority | ID | Title | Board |", _backlog_rows(pools["backlog"])
            ),
        ),
        *_section("🟢 Completed", _items(_newest_first(completed))),
        *_section("✅ Fixed bugs", _items(_newest_first(fixed_bugs))),
        *_section("❌ Cancelled", _items(_newest_first(pools["cancelled"]))),
        *_section("📜 Earlier, written by hand", _history_links(tasks_dir)),
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    tasks_dir = repo_root() / "Tasks"
    board = render_board(tasks_dir)
    if "--write" in argv:
        (tasks_dir / BOARD_FILE).write_text(board, "utf-8")
    else:
        sys.stdout.write(board)
    missing = missing_board_lines(tasks_dir)
    for link in missing:
        sys.stderr.write(f"no **Board:** line: Tasks/{link}\n")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
