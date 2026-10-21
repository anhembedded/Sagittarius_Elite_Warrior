"""`EPIC-045B` - `IBotKind.exposure_left`: closed by default, and the Grid reads its own record."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exposure_left import (
    grid_exposure_left,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    StubKind,
)


def test_a_kind_that_has_declared_nothing_keeps_a_bot_that_ran() -> None:
    sentence = StubKind("martingale").exposure_left("BTCUSDT", {"anything": "here"})

    assert sentence is not None
    assert "martingale" in sentence and "Bots tab" in sentence


def test_a_kind_that_has_declared_nothing_forgets_a_bot_that_never_ran() -> None:
    assert StubKind("martingale").exposure_left("BTCUSDT", {}) is None


def test_a_grid_record_with_no_field_at_all_holds_nothing() -> None:
    assert grid_exposure_left("BTCUSDT", {}) is None


def test_a_grid_record_whose_levels_are_not_a_list_is_unreadable_and_keeps_the_bot() -> (
    None
):
    sentence = grid_exposure_left("BTCUSDT", {"levels": "oops"})

    assert sentence is not None and "cannot be read" in sentence
