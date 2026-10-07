"""`BOT-171` — "put this draft on another Spot venue", through the use case."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
    ChangeBotVenueCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed

S = BotLifecycleState
MAINNET = TradingVenue.SPOT_MAINNET


def _venue_of(store: FakeBotStore, bot_id: str) -> TradingVenue:
    return store.load(BotId(bot_id)).bot.definition.venue


def test_a_draft_is_saved_on_the_other_spot_venue_with_its_parameters_and_runtime() -> (
    None
):
    store = FakeBotStore()
    seed(store, "abc123", S.DRAFT, {"lower": "60000"})

    result = ChangeBotVenueCommandHandler(store).execute(
        ChangeBotVenueCommand("abc123", MAINNET)
    )

    assert result.accepted
    kept = store.load(BotId("abc123"))
    assert kept.bot.definition.venue is MAINNET
    assert kept.bot.state is S.DRAFT
    assert dict(kept.bot.definition.config) == {"lower": "60000"}
    assert kept.runtime == {"cycles": 1}


@pytest.mark.parametrize(
    "state", [s for s in S if s is not S.DRAFT], ids=lambda s: s.value
)
def test_a_bot_that_has_run_or_runs_refuses_and_nothing_changes(state: S) -> None:
    store = FakeBotStore()
    seed(store, "abc123", state)

    result = ChangeBotVenueCommandHandler(store).execute(
        ChangeBotVenueCommand("abc123", MAINNET)
    )

    assert not result.accepted
    assert result.refusal is BotRefusal.VENUE_FIXED
    assert "fixed once it has run" in result.message
    assert _venue_of(store, "abc123") is TradingVenue.SPOT_TESTNET


def test_a_venue_that_is_not_spot_is_refused() -> None:
    store = FakeBotStore()
    seed(store, "abc123", S.DRAFT)

    result = ChangeBotVenueCommandHandler(store).execute(
        ChangeBotVenueCommand("abc123", TradingVenue.FUTURES_TESTNET)
    )

    assert result.refusal is BotRefusal.VENUE_FIXED
    assert _venue_of(store, "abc123") is TradingVenue.SPOT_TESTNET


def test_the_venue_it_is_already_on_is_accepted_and_changes_nothing() -> None:
    store = FakeBotStore()
    seed(store, "abc123", S.RUNNING)

    result = ChangeBotVenueCommandHandler(store).execute(
        ChangeBotVenueCommand("abc123", TradingVenue.SPOT_TESTNET)
    )

    assert result.accepted


def test_a_bot_that_is_not_there_is_refused_as_not_found() -> None:
    result = ChangeBotVenueCommandHandler(FakeBotStore()).execute(
        ChangeBotVenueCommand("nope00", MAINNET)
    )

    assert result.refusal is BotRefusal.NOT_FOUND
