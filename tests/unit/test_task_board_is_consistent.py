"""No two task files may claim the same ID, and no board link may dangle.

The `Tasks/` boards are maintained by hand, and hand-numbering has now failed
four separate times in this repository:

- `BUG-051`/`BUG-052`, two sessions taking "the next number" from the same
  board (recorded at the top of `Tasks/bug_report/README.md`);
- `BUG-058`, which then collided again with the very bug that renumbering
  produced;
- `BOT-120`, two finished tasks sharing a number with only one of them linked
  from `ROADMAP.md`;
- `BOT-126`, a parallel session numbering against a board this session had not
  yet written to.

`Tasks/bug_report/README.md` already says the Engine repo guards exactly this
and that this repo does not. It does now. The check is mechanical because the
failure is mechanical: nobody reads a whole board before picking a number, and
a collision is invisible until two branches meet.

Ignoring `reports/` and `plans/` is deliberate, not an oversight: a report is
*named after* the task it analyses (`BOT-098A_marker_density_performance.md`),
so sharing that ID is the convention rather than a clash. Sub-task IDs are
whole IDs of their own — `BOT-042A` does not collide with `BOT-042`.
"""

from __future__ import annotations

import collections
import hashlib
import re
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts.render_board import (
    ENTRY_ID,
    HISTORY_DIR,
    missing_board_lines,
    render_board,
)
from Sagittarius_Elite_Warrior.scripts.render_task_counts import POOLS, TOTAL_LABEL

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TASKS = _REPO_ROOT / "Tasks"

#: Every directory that holds a real task/bug file. A file's *state* is its
#: directory, so the same ID appearing in two of these is a genuine clash — and
#: so is the same ID twice in one of them.
_FLAT_POOLS = (
    "backlog",
    "completed",
    "in_progress",
    "cancelled",
    "proposal",
    "bug_report/incomplete",
    "bug_report/completed",
)

#: Per-epic sub-task directories, under `Tasks/epics/EPIC-XXX_*/`.
_EPIC_POOLS = ("incomplete", "completed", "cancelled")

#: The renderer's own id pattern, so the two can never disagree on which files
#: are tasks (`BOT-098F6E` once matched neither).
_ID = ENTRY_ID


def _task_files() -> list[Path]:
    found: list[Path] = []
    for pool in _FLAT_POOLS:
        found.extend((_TASKS / pool).glob("*.md"))
    for epic in _TASKS.glob("epics/EPIC-*"):
        for pool in _EPIC_POOLS:
            found.extend((epic / pool).glob("*.md"))
    return found


def _by_id() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = collections.defaultdict(list)
    for path in _task_files():
        match = _ID.match(path.name)
        if match:
            index[match.group(1)].append(path)
    return index


def test_the_scan_actually_finds_the_boards() -> None:
    """Guards the guard. A wrong root or a renamed directory would make every
    assertion below pass over an empty set — green, and proving nothing."""
    assert len(_task_files()) > 100


def test_no_two_task_files_share_an_id() -> None:
    """The collision itself. Two files with one ID means one of them is
    invisible on the board, and a link to that ID reaches whichever the writer
    happened to mean."""
    clashes = {
        task_id: sorted(str(p.relative_to(_REPO_ROOT)) for p in paths)
        for task_id, paths in _by_id().items()
        if len(paths) > 1
    }

    assert clashes == {}, (
        "these IDs are used by more than one task file — renumber the one with "
        f"fewer references and record the change in its own header: {clashes}"
    )


def test_every_task_and_bug_file_carries_its_board_line() -> None:
    """The other half of the two checks above. A dangling link is a row with no
    file; this is a file with no row, which reads, to anyone who only opens
    the board, as a task that does not exist. The board is generated from each
    file's `**Board:**` field (`BOT-163`), so the file must carry one; a closed
    file the frozen history in `Tasks/history/` already lists is exempt, an
    open one never is."""
    missing = missing_board_lines(_TASKS)

    assert missing == [], (
        "task or bug files with no `**Board:**` line: add the one line the board "
        f"shows for it (ONBOARDING §6): {missing}"
    )


#: The hand-written boards. A list or a count table written into either brings
#: back the shared lines every pull request edited (`BOT-163`).
_HAND_WRITTEN_BOARDS = ("ROADMAP.md", "bug_report/README.md")

#: A list item (bulleted or numbered) or a table row that names a task or bug:
#: the shape of every listed entry, whatever its link. Prose and blockquotes
#: may still cite a task.
_LISTED = re.compile(r"^\s*(?:[-*+]|\d+[.)]|\|).*?(?<![A-Za-z0-9])[A-Z]+-\d+(?![a-z])")


@pytest.mark.parametrize(
    ("line", "listed"),
    [
        ("- [x] **BOT-300** done", True),
        ("| BOT-301 | `backlog/BOT-301_x.md` |", True),
        ("- [BOT-302](epics/EPIC-1/completed/a.md)", True),
        ("1. [BOT-303](completed/BOT-303_x.md)", True),
        ("  + [BOT-304](completed/x.md)", True),
        ("| ✅ **[BOT-098F6E](completed/x.md)** |", True),
        ("> The owner settled it in `BOT-008`.", False),
        ("| 🟢 **`S (Fast Agent)`** | **Fast** *(GPT-4o-mini)* |", False),
        ("- **Names:** `BUG-XXX_slug.md`, numbered one above the highest.", False),
    ],
)
def test_a_listed_entry_is_caught_in_every_list_shape(line: str, listed: bool) -> None:
    assert bool(_LISTED.search(line)) is listed


def test_no_board_list_is_written_by_hand() -> None:
    labels = [label for _, label in POOLS] + [TOTAL_LABEL]
    found: list[str] = []
    for name in _HAND_WRITTEN_BOARDS:
        for number, line in enumerate(
            (_TASKS / name).read_text("utf-8").splitlines(), 1
        ):
            if any(label in line for label in labels) or _LISTED.search(line):
                found.append(f"{name}:{number}: {line[:80]}")

    assert found == [], (
        "a list or count table is written into a hand-written board; it is generated "
        f"by `python3 scripts/render_board.py` from the files instead ({len(found)} "
        f"lines): {found[:10]}"
    )


#: The hand-written boards frozen when the boards became generated, by the
#: SHA-256 of their text with `\n` line ends (a Windows checkout writes `\r\n`).
_FROZEN_HISTORY = {
    "BUG_BOARD_until_2026-10-06.md": "1a2ca27d243c415efb671071213aa8ebe3d2b1b79904d0e18e9dce324c335bcd",
    "ROADMAP_until_2026-10-06.md": "970a3f82cb7e34814f324acca56501453025a5fdede57aa4b03cce1c04629f51",
}


def test_the_history_is_frozen() -> None:
    """A closed file the history lists needs no `**Board:**` line, so an edit
    to the history would change what the board shows without touching a task
    file. Nothing is ever added to it; a new entry is a file's board line."""
    found = {
        path.name: hashlib.sha256(
            path.read_text("utf-8").replace("\r\n", "\n").encode("utf-8")
        ).hexdigest()
        for path in sorted((_TASKS / HISTORY_DIR).glob("*.md"))
    }

    assert found == _FROZEN_HISTORY, (
        "Tasks/history/ changed; it is frozen: write the change into the task or "
        "bug file's own `**Board:**` line instead"
    )


def test_every_epic_sub_task_is_mentioned_in_its_epic_readme() -> None:
    """Same check, one level down: an epic's `README.md` is its board
    (`Tasks/epics/README.md`, "Thư mục là nguồn sự thật mà người ta *liệt kê*,
    README là thứ người ta *đọc*")."""
    invisible: list[str] = []
    for epic in sorted(_TASKS.glob("epics/EPIC-*")):
        readme = (epic / "README.md").read_text("utf-8")
        for pool in _EPIC_POOLS:
            for path in sorted((epic / pool).glob("*.md")):
                match = _ID.match(path.name)
                if match and match.group(1) not in readme:
                    invisible.append(str(path.relative_to(_TASKS)))

    assert invisible == [], (
        f"epic sub-task files not mentioned by id in their epic's README.md: {invisible}"
    )


def test_every_board_link_resolves() -> None:
    """A renumber that misses a link leaves the board pointing at a file that
    no longer exists — which reads exactly like a task nobody finished."""
    boards = [
        (_TASKS / name, (_TASKS / name).read_text("utf-8"))
        for name in _HAND_WRITTEN_BOARDS
    ]
    # The generated board's links come from the files' `**Board:**` lines.
    boards.append((_TASKS / "BOARD.md", render_board(_TASKS)))
    dangling: list[str] = []
    for board, text in boards:
        for target in re.findall(r"\]\(([^)#][^)]*\.md)\)", text):
            if not (board.parent / target).exists():
                dangling.append(f"{board.name} -> {target}")

    assert dangling == [], f"board links pointing at nothing: {dangling}"
