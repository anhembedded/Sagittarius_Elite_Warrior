"""`EPIC-042B` - a hand-written set of states that names HALTED also answers for AWAITING_RECOVERY.

The lifecycle table makes the enable-rules and the sets derived from it (`PRICE_STREAM_STATES`,
`restarts_into_recovering`) answer for a new state by themselves. A set or a comparison written by
hand does not: the review of ADR 042 found a dozen of them, and the worst would have skipped the
real-money confirmation of a mainnet Resume. This guard reads every file of `src/modules/bots/`
with `ast` and fails when one names `BotLifecycleState.HALTED` and neither names
`AWAITING_RECOVERY` nor asks `RESUME_PROPOSES_STATES`, unless the file is in `_EXCEPTIONS` with the
reason HALTED alone is right there.

The exceptions only shrink: an entry whose file no longer names HALTED alone fails as stale.

Retire when: the lifecycle states are a closed `match` the type checker proves exhaustive.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BOTS = _REPO_ROOT / "src" / "modules" / "bots"

#: The spellings of the enum in this module: the class and the `_S` alias the Grid files use.
_ENUM_NAMES = frozenset({"BotLifecycleState", "_S"})

#: File (relative to `src/modules/bots/`) -> why HALTED alone is the right answer there.
_EXCEPTIONS: dict[str, str] = {
    "application/kinds/grid/start/grid_interrupted_start.py": (
        "a start cut short owes a cancel and ends HALTED; AWAITING_RECOVERY never owes one"
    ),
    "application/services/lifecycle/bot_boot_recovery.py": (
        "pays the cancel a cut-short start owes; only HALTED owes it"
    ),
    "ui/bots_screen/preview_frames.py": "builds a HALTED sample bot for the preview",
}


def answers(source: str) -> tuple[bool, bool]:
    """(names HALTED, answers for AWAITING_RECOVERY) in `source`."""
    names_halted = answers_for_waiting = False
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            if (
                node.attr == "HALTED"
                and isinstance(node.value, ast.Name)
                and node.value.id in _ENUM_NAMES
            ):
                names_halted = True
            elif node.attr == "AWAITING_RECOVERY":
                answers_for_waiting = True
        elif isinstance(node, ast.Name) and node.id == "RESUME_PROPOSES_STATES":
            answers_for_waiting = True
    return names_halted, answers_for_waiting


def _bots_files() -> list[Path]:
    return sorted(p for p in _BOTS.rglob("*.py") if "__pycache__" not in p.parts)


def _relative(path: Path) -> str:
    return path.relative_to(_BOTS).as_posix()


def test_the_scan_finds_the_bots_files() -> None:
    assert _bots_files()


def test_a_file_naming_halted_answers_for_awaiting_recovery_or_is_excepted() -> None:
    unanswered = []
    for path in _bots_files():
        halted, waiting = answers(path.read_text(encoding="utf-8"))
        if halted and not waiting and _relative(path) not in _EXCEPTIONS:
            unanswered.append(_relative(path))
    assert not unanswered, (
        "these files name HALTED but not AWAITING_RECOVERY (ADR 042 §2.4): add the state to "
        f"the set, ask RESUME_PROPOSES_STATES, or explain in _EXCEPTIONS: {unanswered}"
    )


def test_every_exception_is_still_needed() -> None:
    stale = []
    for relative in _EXCEPTIONS:
        halted, waiting = answers((_BOTS / relative).read_text(encoding="utf-8"))
        if not halted or waiting:
            stale.append(relative)
    assert not stale, f"drop these from _EXCEPTIONS, they no longer need it: {stale}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("S = {BotLifecycleState.HALTED}", (True, False)),
        ("S = {_S.HALTED, _S.AWAITING_RECOVERY}", (True, True)),
        ("S = RESUME_PROPOSES_STATES | {BotLifecycleState.HALTED}", (True, True)),
        ("S = {Other.HALTED}", (False, False)),
        ("# BotLifecycleState.HALTED in a comment", (False, False)),
    ],
)
def test_the_scan_reads_the_syntax_not_the_words(
    source: str, expected: tuple[bool, bool]
) -> None:
    assert answers(source) == expected
