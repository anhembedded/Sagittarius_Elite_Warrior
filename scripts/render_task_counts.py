"""The task-count table of the generated board, computed from the directories.

`scripts/render_board.py` renders it at the top of the board (`BOT-163`); a task
moved between folders changes the count with nothing else to edit. Bug reports
are not counted (they are listed on their own).

Usage:
    python3 scripts/render_task_counts.py
"""

from __future__ import annotations

from pathlib import Path

#: (directory under Tasks/, the row label on the board).
POOLS: tuple[tuple[str, str], ...] = (
    ("completed", "🟢 **Completed**"),
    ("in_progress", "🟡 **In Progress**"),
    ("backlog", "🔴 **Backlog**"),
    ("cancelled", "❌ **Cancelled**"),
)
TOTAL_LABEL = "📈 **Tổng số Task**"


def repo_root() -> Path:
    """The repository root, found by landmark rather than by hop count."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("pyproject.toml not found above this script")


def count_tasks(tasks_dir: Path) -> dict[str, int]:
    """Number of task files per pool; an absent pool counts as empty."""
    return {pool: len(list((tasks_dir / pool).glob("*.md"))) for pool, _ in POOLS}


def render_rows(counts: dict[str, int]) -> list[str]:
    """The five table rows of the board's count table."""
    total = sum(counts.values())
    rows = []
    for pool, label in POOLS:
        share = (counts[pool] / total * 100) if total else 0.0
        rows.append(f"| {label} | {counts[pool]} | {share:.1f}% |")
    rows.append(f"| {TOTAL_LABEL} | **{total}** | **100%** |")
    return rows


def main() -> int:
    print("\n".join(render_rows(count_tasks(repo_root() / "Tasks"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
