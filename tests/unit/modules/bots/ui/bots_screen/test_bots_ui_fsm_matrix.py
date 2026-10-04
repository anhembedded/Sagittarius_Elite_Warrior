"""`EPIC-029F` — the screen's own modes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_ui_fsm_matrix import (
    BOTS_UI_TRANSITIONS,
    BotsUiEvent,
    BotsUiState,
    selection_event,
    settled_event,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

U = BotsUiState
E = BotsUiEvent


def _bot(state: BotLifecycleState) -> BotSnapshot:
    return BotSnapshot(
        "a00001",
        "g",
        "grid",
        TradingVenue.SPOT_TESTNET,
        "BTCUSDT",
        state,
        datetime(2026, 10, 4, tzinfo=UTC),
        None,
    )


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (BotLifecycleState.DRAFT, E.SELECTED_DRAFT),
        (BotLifecycleState.STOPPED, E.SELECTED_DRAFT),
        (BotLifecycleState.RUNNING, E.SELECTED_BOT),
        (BotLifecycleState.HALTED, E.SELECTED_BOT),
    ],
    ids=lambda value: getattr(value, "value", value),
)
def test_a_bot_whose_table_declares_edit_opens_for_editing(
    state: BotLifecycleState, event: BotsUiEvent
) -> None:
    assert selection_event(_bot(state)) is event


def test_nothing_selected_is_its_own_mode() -> None:
    assert selection_event(None) is E.SELECTED_NONE
    assert settled_event(None) is E.SETTLED_NONE


def test_an_action_in_flight_ignores_selection_and_settles_on_the_selection() -> None:
    for selected in (E.SELECTED_NONE, E.SELECTED_BOT, E.SELECTED_DRAFT):
        assert (U.ACTION_IN_FLIGHT, selected) not in BOTS_UI_TRANSITIONS
    assert BOTS_UI_TRANSITIONS[(U.ACTION_IN_FLIGHT, E.SETTLED_BOT)] is U.VIEWING
    assert BOTS_UI_TRANSITIONS[(U.ACTION_IN_FLIGHT, E.SETTLED_DRAFT)] is U.EDITING_DRAFT
    assert settled_event(_bot(BotLifecycleState.RUNNING)) is E.SETTLED_BOT


def test_a_second_action_cannot_start_while_one_is_in_flight() -> None:
    assert (U.ACTION_IN_FLIGHT, E.ACTION_STARTED) not in BOTS_UI_TRANSITIONS
    for mode in (U.NO_SELECTION, U.VIEWING, U.EDITING_DRAFT):
        assert BOTS_UI_TRANSITIONS[(mode, E.ACTION_STARTED)] is U.ACTION_IN_FLIGHT
