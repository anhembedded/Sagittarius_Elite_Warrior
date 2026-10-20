"""`BOT-206` — each frame of the Plan dock's property table says what its name promises.

@details A frame is the real screen filled from a bot snapshot, so each test reads what the table
on a frame shows, not that the frame built."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    READINESS_GROUP,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_table_frames import (
    FRAMES,
    build_frame,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _frame(qtbot, name: str) -> BotsView:
    view = build_frame(name)
    qtbot.addWidget(view)
    view.show()
    assert isinstance(view, BotsView)
    return view


def test_the_three_states_the_owner_asked_to_see_have_a_frame() -> None:
    assert set(FRAMES) == {"draft_blocked", "futures_running", "spot_running"}


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_each_frame_builds_and_draws_the_whole_table(qtbot, name: str) -> None:
    view = _frame(qtbot, name)
    table = view.plan.properties.view

    assert not view.grab().isNull()
    assert view.model.selected is not None
    # The window is tall enough for the dock to show every row without a scroll, once the
    # layout the rows' wrapped heights ask for has run.
    qtbot.waitUntil(
        lambda: (
            table.visibleRegion().boundingRect().height()
            >= table.sizeHint().height() - 2
        )
    )


def test_the_draft_frame_has_its_blocking_reason_above_the_table_and_a_readiness_group(
    qtbot,
) -> None:
    view = _frame(qtbot, "draft_blocked")
    plan = view.plan

    assert "above the 800.00 USDT available" in plan.readiness_items.text()
    assert plan.readiness_marker.isVisible()
    assert plan.properties.group_is_shown(READINESS_GROUP)
    assert plan.properties.shown_value("step_design") == "1 thing left"
    assert plan.properties.shown_value("step_run") == "waits for Design"


def test_the_futures_frame_shows_a_position_its_costs_and_a_liquidation_row(
    qtbot,
) -> None:
    view = _frame(qtbot, "futures_running")
    figures = view.plan.properties

    assert view.model.selected.venue is TradingVenue.FUTURES_TESTNET
    assert not figures.group_is_shown(READINESS_GROUP)
    assert figures.shown_value("inventory").startswith("0.0615 at an average")
    assert figures.row_is_shown("commissions") and figures.row_is_shown("funding")
    assert figures.row_is_shown("liquidation")
    assert figures.shown_value("last_price").endswith("40 s ago")


def test_the_spot_frame_has_no_cost_or_liquidation_rows(qtbot) -> None:
    view = _frame(qtbot, "spot_running")
    figures = view.plan.properties

    assert view.model.selected.venue is TradingVenue.SPOT_TESTNET
    assert figures.row_is_shown("grid_profit")
    assert not figures.row_is_shown("commissions")
    assert not figures.row_is_shown("liquidation")
    assert figures.shown_value("last_price").endswith("2 min ago")
