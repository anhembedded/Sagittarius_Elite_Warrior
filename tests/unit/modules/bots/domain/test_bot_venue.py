"""`BOT-171` — a bot's venue is fixed once it has run; a draft that never ran may move
between the Spot venues, and no other bot may."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
    BotVenueFixedError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

S = BotLifecycleState
T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def _bot(
    state: S = S.DRAFT,
    *,
    ran: bool = False,
    venue: TradingVenue = TradingVenue.SPOT_TESTNET,
) -> Bot:
    definition = BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"})
    lifecycle = BotLifecycle(state, T0 if ran else None)
    return Bot(BotId("abc123"), definition, lifecycle, T0)


@pytest.mark.parametrize(
    ("origin", "target"),
    [
        (TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET),
        (TradingVenue.SPOT_MAINNET, TradingVenue.SPOT_TESTNET),
    ],
)
def test_a_draft_that_never_ran_moves_between_the_spot_venues(
    origin: TradingVenue, target: TradingVenue
) -> None:
    bot = _bot(venue=origin)

    moved = bot.moved_to(target)

    assert bot.venue_locked_reason == ""
    assert moved.definition.venue is target
    assert moved.state is S.DRAFT
    assert bot.definition.venue is origin
    assert dict(moved.definition.config) == dict(bot.definition.config)


@pytest.mark.parametrize(
    "state", [s for s in S if s is not S.DRAFT], ids=lambda s: s.value
)
def test_a_bot_that_is_not_a_draft_keeps_its_venue(state: S) -> None:
    bot = _bot(state, ran=True)

    assert bot.venue_locked_reason
    with pytest.raises(BotVenueFixedError, match="fixed once it has run"):
        bot.moved_to(TradingVenue.SPOT_MAINNET)


def test_a_draft_edited_back_from_stopped_has_run_and_keeps_its_venue() -> None:
    """EDIT lands a STOPPED bot on DRAFT, but the run it had stays recorded."""
    stopped = _bot(S.STOPPED, ran=True)
    edited = stopped.apply(BotLifecycleEvent.EDIT, T0)

    assert edited.state is S.DRAFT
    assert edited.venue_locked_reason
    with pytest.raises(BotVenueFixedError):
        edited.moved_to(TradingVenue.SPOT_MAINNET)


@pytest.mark.parametrize(
    "target",
    [
        TradingVenue.FUTURES_TESTNET,
        TradingVenue.FUTURES_MAINNET,
        TradingVenue.DISABLED,
    ],
)
def test_a_spot_draft_is_never_moved_to_a_venue_that_is_not_spot(
    target: TradingVenue,
) -> None:
    with pytest.raises(BotVenueFixedError, match="not a Spot venue"):
        _bot().moved_to(target)


def test_a_futures_bot_does_not_change_venue_here() -> None:
    """Futures grid bots are `EPIC-029K`."""
    bot = _bot(venue=TradingVenue.FUTURES_TESTNET)

    assert "Only a Spot bot" in bot.venue_locked_reason
    with pytest.raises(BotVenueFixedError):
        bot.moved_to(TradingVenue.SPOT_TESTNET)
