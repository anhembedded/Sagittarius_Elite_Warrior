"""Print the task-count table `Tasks/ROADMAP.md` must carry, computed from the directories.

`ONBOARDING.md` §6 requires the count table to be recomputed from disk, never by hand;
`tests/unit/test_task_board_is_consistent.py` fails when the committed table disagrees with
this function's output. Bug reports are not counted (they have their own board).

Usage:
    python3 scripts/render_task_counts.py
"""

from __future__ import annotations

from pathlib import Path

#: (directory under Tasks/, the row label as it appears in ROADMAP.md).
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
    """The five table rows, formatted exactly as `Tasks/ROADMAP.md` carries them."""
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
