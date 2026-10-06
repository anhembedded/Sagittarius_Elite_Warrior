"""`BOT-163`: the board is rendered from each file's own `**Board:**` line.

Every test builds a small `Tasks/` tree under `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_board import (
    missing_board_lines,
    read_entry,
    render_board,
)


def _task(tasks: Path, pool: str, name: str, *fields: str, heading: str = "") -> Path:
    path = tasks / pool / name
    path.parent.mkdir(parents=True, exist_ok=True)
    entry_id = name.split("_")[0]
    title = heading or f"{entry_id} — The outcome of {entry_id}"
    path.write_text(f"# {title}\n\n" + "".join(f"{f}\n" for f in fields), "utf-8")
    return path


def _history(tasks: Path, text: str) -> None:
    (tasks / "history").mkdir(parents=True, exist_ok=True)
    (tasks / "history" / "ROADMAP_until_2026-10-06.md").write_text(text, "utf-8")


def test_an_entry_reads_its_fields_and_drops_the_id_from_its_title(tmp_path):
    path = _task(
        tmp_path,
        "completed",
        "BOT-200_x.md",
        "**Status:** ✅ Done (2026-10-07)",
        "**Board:** Decision: one table.",
    )

    entry = read_entry(path, tmp_path)

    assert entry is not None
    assert (entry.entry_id, entry.title, entry.date, entry.board) == (
        "BOT-200",
        "The outcome of BOT-200",
        "2026-10-07",
        "Decision: one table.",
    )
    assert entry.link == "completed/BOT-200_x.md"


def test_a_bug_reads_its_bulleted_fields(tmp_path):
    path = _task(
        tmp_path,
        "bug_report/incomplete",
        "BUG-300_x.md",
        "- **Severity:** 🟡 P2",
        "- **Status:** Open",
        "- **Board:** It crashes.",
    )

    entry = read_entry(path, tmp_path)

    assert entry is not None
    assert (entry.severity, entry.board) == ("🟡 P2", "It crashes.")


def test_a_file_without_an_id_is_not_an_entry(tmp_path):
    assert read_entry(_task(tmp_path, "backlog", "notes.md"), tmp_path) is None


def test_completed_entries_read_newest_first(tmp_path):
    for entry_id, day in (("BOT-201", "2026-10-01"), ("BOT-202", "2026-10-05")):
        _task(
            tmp_path,
            "completed",
            f"{entry_id}_x.md",
            f"**Status:** ✅ Done ({day})",
            f"**Board:** line of {entry_id}",
        )

    board = render_board(tmp_path)

    assert board.index("line of BOT-202") < board.index("line of BOT-201")


def test_a_sub_task_id_with_letters_and_digits_is_an_entry(tmp_path):
    path = _task(tmp_path, "backlog", "BOT-098F6E_x.md", "**Board:** native rollout")

    entry = read_entry(path, tmp_path)

    assert entry is not None
    assert entry.entry_id == "BOT-098F6E"
    assert "native rollout" in render_board(tmp_path)


def test_a_pool_file_not_named_by_an_id_is_missing(tmp_path):
    _task(tmp_path, "backlog", "notes.md", "**Board:** looks like a task")

    assert missing_board_lines(tmp_path) == ["backlog/notes.md (not named by an id)"]


def test_an_epic_child_stays_on_its_epic_board(tmp_path):
    """An epic's README is its children's board, guarded on its own."""
    _task(
        tmp_path,
        "epics/EPIC-040_x/completed",
        "EPIC-040A_x.md",
        "**Board:** the child's decision",
    )

    assert "EPIC-040A" not in render_board(tmp_path)


def test_the_backlog_reads_by_priority_then_id(tmp_path):
    _task(tmp_path, "backlog", "BOT-210_x.md", "**Board:** unranked")
    _task(tmp_path, "backlog", "BOT-211_x.md", "**Priority:** P3", "**Board:** low")
    _task(tmp_path, "backlog", "BOT-212_x.md", "**Priority:** P1", "**Board:** high")
    _task(
        tmp_path,
        "backlog",
        "BOT-209_x.md",
        "**Priority:** Deferred (was P1)",
        "**Board:** later",
    )

    board = render_board(tmp_path)

    assert (
        board.index("| high |")
        < board.index("| low |")
        < board.index("| later |")
        < board.index("| unranked |")
    )


def test_the_counts_come_from_the_folders(tmp_path):
    _task(tmp_path, "backlog", "BOT-220_x.md", "**Board:** a")
    _task(tmp_path, "completed", "BOT-221_x.md", "**Board:** b")
    _task(tmp_path, "completed", "BOT-222_x.md", "**Board:** c")

    board = render_board(tmp_path)

    assert "| 🟢 **Completed** | 2 | 66.7% |" in board
    assert "| 🔴 **Backlog** | 1 | 33.3% |" in board


def test_an_open_file_without_a_board_line_is_missing(tmp_path):
    _task(tmp_path, "backlog", "BOT-230_x.md", "**Status:** 🔵 Backlog")
    _task(tmp_path, "bug_report/incomplete", "BUG-231_x.md", "- **Status:** Open")
    # The history naming them does not excuse an open file.
    _history(tmp_path, "BOT-230 and BUG-231 were listed here.")

    assert missing_board_lines(tmp_path) == [
        "backlog/BOT-230_x.md",
        "bug_report/incomplete/BUG-231_x.md",
    ]


def test_a_closed_file_the_history_lists_needs_no_board_line(tmp_path):
    _task(tmp_path, "completed", "BOT-240C_x.md", "**Status:** ✅ Done")
    _task(tmp_path, "cancelled", "BOT-241_x.md", "**Status:** ❌ Cancelled")
    _history(tmp_path, "- [x] [Old](../completed/BOT-240C_x.md)\n")

    assert missing_board_lines(tmp_path) == ["cancelled/BOT-241_x.md"]


def test_an_id_inside_a_longer_id_is_not_a_mention(tmp_path):
    _task(tmp_path, "completed", "BOT-250_x.md", "**Status:** ✅ Done")
    _history(tmp_path, "Only BOT-2501, BOT-250A and xBOT-250 are listed.")

    assert missing_board_lines(tmp_path) == ["completed/BOT-250_x.md"]


def test_the_board_links_the_frozen_history(tmp_path):
    _history(tmp_path, "old board")

    assert (
        "- [ROADMAP_until_2026-10-06](history/ROADMAP_until_2026-10-06.md)"
        in render_board(tmp_path)
    )
