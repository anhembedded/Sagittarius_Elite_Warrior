"""A test file under `src/` is a test the gate never runs — `BUG-128`, `CS-004`.

The gate's command is `pytest Sagittarius_Elite_Warrior/tests`. A file named
`test_*.py` anywhere under `src/` is therefore collected by nobody: it looks
like coverage in a directory listing, it can be read and cited as coverage, and
it asserts nothing on any run that decides whether the code ships.

PR 1.4b-2 found this and counted the files. `BUG-128` is the first time it cost
something: `TimeRangePickerVM`'s thirteen tests lived at
`src/presentation/ui/qml/TimeRangePicker/tests/test_time_range_picker_vm.py`,
the host test's own docstring cited them as *"full coverage with no
`QApplication` at all"*, and the inverted-range branch of `refresh()`'s
three-part condition was never covered by any of them — nor would it have
mattered if it had been.

## Why a shrink-only baseline instead of zero

Every remaining file is inside a QML package ADR D21 **deletes** rather than
moves, and they go with their `.qml` over `EPIC-025` PR 4.3's remaining steps.
Demanding zero today would mean either deleting those packages early (Phase 4's
work done out of order, against the Strangler Fig rule that the app keeps
running at every step) or moving tests whose subject is about to be deleted.
So the list may only ever get shorter, the same shape as
`baseline_qml_files.txt`, and it reaches zero when the last `.qml` goes.

Stdlib only, like the other path guards here.
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    """By landmark, not by hop count (`test_no_root_is_found_by_counting.py`)."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


_REPO_ROOT = _repo_root()
_SRC = _REPO_ROOT / "src"
_BASELINE_FILE = Path(__file__).with_name("baseline_tests_under_src.txt")

#: A file whose name makes pytest collect it, plus `conftest.py`, which only
#: exists to serve such files and is dead weight without them.
_TEST_FILE_PATTERNS = ("test_*.py", "*_test.py", "conftest.py")


def _tests_under_src() -> list[str]:
    found: set[str] = set()
    for pattern in _TEST_FILE_PATTERNS:
        for path in _SRC.rglob(pattern):
            if "__pycache__" in path.parts:
                continue
            found.add(path.relative_to(_REPO_ROOT).as_posix())
    return sorted(found)


def _baseline() -> list[str]:
    return sorted(
        line.strip()
        for line in _BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


def test_no_test_file_appears_under_src_that_the_baseline_does_not_list() -> None:
    """A new one is never acceptable: it would be unrunnable the day it is
    written."""
    added = sorted(set(_tests_under_src()) - set(_baseline()))

    assert added == [], (
        "these test files are under `src/`, where the gate "
        "(`pytest Sagittarius_Elite_Warrior/tests`) never collects them:\n  "
        + "\n  ".join(added)
        + "\nPut them under `tests/`. A test the gate cannot run is not coverage."
    )


def test_the_baseline_was_lowered_when_a_file_went() -> None:
    """The list only shrinks, and a step that shrinks it lowers it in the same
    commit — otherwise the number stops describing the tree and the next
    reader trusts a stale one (`ci-rule.md` §5.5)."""
    removed = sorted(set(_baseline()) - set(_tests_under_src()))

    assert removed == [], (
        f"{len(removed)} file(s) in {_BASELINE_FILE.name} no longer exist — "
        "delete their lines in the same commit:\n  " + "\n  ".join(removed)
    )


def test_the_guard_has_a_subject() -> None:
    """`src/` moving would make both checks above pass over an empty scan."""
    assert _SRC.is_dir(), f"{_SRC} is not a directory — this guard reads nothing"
    assert (_SRC / "support").is_dir(), (
        "src/support is missing; src/ is not the tree this guard was written for"
    )
