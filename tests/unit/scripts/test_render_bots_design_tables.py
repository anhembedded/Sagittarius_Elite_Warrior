"""The bots design's generated tables cannot differ from the code (`EPIC-041E`).

`Docs/MODULES/bots/state-machines.md` holds the two transition tables and
`10-quality.md` the timing table, each between a pair of markers that
`scripts/render_bots_design_tables.py --write` rewrites. A hand edit, a transition
added to a `*_fsm_matrix.py` or a constant changed without regenerating fails here.
"""

from __future__ import annotations

import shutil
from datetime import timedelta
from enum import Enum
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts import render_bots_design_tables as render
from Sagittarius_Elite_Warrior.scripts.render_bots_design_tables import (
    TIMING,
    Constant,
    TimingRow,
    blocks,
    committed_block,
    render_timing,
    render_transitions,
    replace_block,
    seconds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BOT_LIFECYCLE_TRANSITIONS,
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    GRID_LEVEL_TRANSITIONS,
    LevelEvent,
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)

_BLOCKS = blocks()


@pytest.mark.parametrize(
    ("document", "name"), list(_BLOCKS), ids=[name for _, name in _BLOCKS]
)
def test_the_committed_table_is_a_fresh_render(document: Path, name: str) -> None:
    """Regenerate with `python3 scripts/render_bots_design_tables.py --write`."""
    committed = committed_block(document.read_text(encoding="utf-8"), name)

    assert committed is not None, f"{document.name} has no `{name}` markers"
    assert committed == _BLOCKS[(document, name)]


def test_every_declared_transition_has_its_row() -> None:
    lifecycle = render_transitions(BOT_LIFECYCLE_TRANSITIONS)
    level = render_transitions(GRID_LEVEL_TRANSITIONS)

    assert all(
        f"| `{state.value}` | `{event.value}` |" in lifecycle
        for state, event in BOT_LIFECYCLE_TRANSITIONS
    )
    assert all(
        f"| `{state.value}` | `{event.value}` |" in level
        for state, event in GRID_LEVEL_TRANSITIONS
    )


def test_a_transition_added_to_the_table_changes_the_render() -> None:
    """The drift probe: a copy of the table with one more row no longer matches
    what is committed, so the drift test above would go red."""
    widened: dict[tuple[Enum, Enum], Enum] = dict(GRID_LEVEL_TRANSITIONS)
    widened[(LevelState.FILLED, LevelEvent.ENDED)] = LevelState.EMPTY

    assert render_transitions(widened) != render_transitions(GRID_LEVEL_TRANSITIONS)
    assert "| `FILLED` | `ended` | `EMPTY` |" in render_transitions(widened)


def test_a_retargeted_transition_changes_the_render() -> None:
    moved: dict[tuple[Enum, Enum], Enum] = dict(BOT_LIFECYCLE_TRANSITIONS)
    moved[(BotLifecycleState.RUNNING, BotLifecycleEvent.HALT)] = BotLifecycleState.ERROR

    assert render_transitions(moved) != render_transitions(BOT_LIFECYCLE_TRANSITIONS)


def test_targets_that_are_not_states_and_self_loops_are_named() -> None:
    lifecycle = render_transitions(BOT_LIFECYCLE_TRANSITIONS)

    assert "| `DRAFT` | `delete` | removed (the file is deleted) |" in lifecycle
    assert "| `RECOVERING` | `reconcile_ok` | the state before the restart" in lifecycle
    assert "| `RECOVERING` | `resume` | `RECOVERING` (stays) |" in lifecycle


@pytest.fixture
def design_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The two generated documents copied to `tmp_path`, and the script pointed at them."""
    for document in (render.STATE_MACHINES, render.QUALITY):
        shutil.copy(document, tmp_path / document.name)
    monkeypatch.setattr(render, "STATE_MACHINES", tmp_path / render.STATE_MACHINES.name)
    monkeypatch.setattr(render, "QUALITY", tmp_path / render.QUALITY.name)
    return tmp_path


def test_check_passes_on_the_committed_documents(design_copy: Path) -> None:
    assert render.main(["--check"]) == 0


def test_check_fails_on_a_hand_edited_value_and_write_repairs_it(
    design_copy: Path,
) -> None:
    """The drift probe on the real document: one timing value edited by hand."""
    quality = design_copy / render.QUALITY.name
    text = quality.read_text(encoding="utf-8")
    assert "| 120 s; 300 s; 15 s |" in text
    quality.write_text(
        text.replace("| 120 s; 300 s; 15 s |", "| 90 s; 300 s; 15 s |"),
        encoding="utf-8",
    )

    assert render.main(["--check"]) == 1

    assert render.main(["--write"]) == 0
    assert render.main(["--check"]) == 0
    assert quality.read_text(encoding="utf-8") == text


def test_check_fails_on_a_dropped_transition_row(design_copy: Path) -> None:
    machines = design_copy / render.STATE_MACHINES.name
    text = machines.read_text(encoding="utf-8")
    row = "| `FILLED` | `settled` | `EMPTY` |\n"
    assert row in text
    machines.write_text(text.replace(row, ""), encoding="utf-8")

    assert render.main(["--check"]) == 1


@pytest.mark.parametrize("row", TIMING, ids=[row.what[:40] for row in TIMING])
def test_every_timing_constant_is_read_from_the_code(row: TimingRow) -> None:
    """A renamed or deleted constant raises here rather than leaving a stale cell, and
    each constant is a duration, a count, a ratio, a tuple of delays or the caps object."""
    for constant in row.constants:
        value = constant.value()
        assert isinstance(value, timedelta | int | float | tuple | OwnerBudgetCaps), (
            f"{constant.path} → {constant.name} is a {type(value).__name__}"
        )
    assert any(character.isdigit() for character in render_timing((row,)))


def test_a_dataclass_default_is_read_from_its_field() -> None:
    constant = Constant(
        "src/modules/bots/application/services/watches/user_stream_watch.py",
        "UserStreamLimits.down_limit",
    )

    assert isinstance(constant.value(), timedelta)


@pytest.mark.parametrize(
    ("value", "written"),
    [
        (timedelta(milliseconds=250), "250 ms"),
        (timedelta(seconds=1), "1 s"),
        (2.0, "2 s"),
        (timedelta(seconds=3599), "3599 s"),
        (timedelta(hours=1), "1 h"),
        (timedelta(seconds=5400), "5400 s"),
        (timedelta(hours=8), "8 h"),
    ],
)
def test_a_duration_is_written_as_a_reader_says_it(value: object, written: str) -> None:
    assert seconds(value) == written


def test_a_block_is_replaced_between_its_markers_only() -> None:
    text = (
        "before\n"
        "<!-- generated by scripts/render_bots_design_tables.py: timing -->\n"
        "old\n"
        "<!-- end generated: timing -->\n"
        "after\n"
    )

    replaced = replace_block(text, "timing", "new\n")

    assert committed_block(replaced, "timing") == "new\n"
    assert replaced.startswith("before\n") and replaced.endswith("after\n")


def test_a_document_without_the_markers_is_refused() -> None:
    with pytest.raises(ValueError, match="no `timing` markers"):
        replace_block("no markers here\n", "timing", "new\n")
