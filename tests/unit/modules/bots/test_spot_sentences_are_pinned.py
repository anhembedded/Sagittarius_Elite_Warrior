"""`EPIC-039A` - moving the Spot comparisons behind the venue profile changed no sentence.

The Spot behaviour is the regression oracle for the Futures work (`EPIC-039`): each sentence a
user or `bot list` can read about a venue is pinned here, whole, for the Spot venues, a Futures
venue and `DISABLED`. A rewording belongs to a task that says so, not to a refactor.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.planner_numbers import (
    read_planner_numbers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_run_facts import (
    BotRunFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
    BotVenueFixedError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

T0 = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
_CAPS = OwnerBudgetCaps(40, timedelta(0), 30)
_NOT_SPOT = [TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET]


class _NoVenueEnabled(IVenueTradingPorts):
    def enabled(self) -> tuple[TradingVenue, ...]:
        return ()

    def get(self, venue: TradingVenue) -> VenueTradingPorts:
        raise AssertionError("a refused venue is not read")

    def primary(self) -> VenueTradingPorts:
        raise AssertionError("not used")


def _bot(venue: TradingVenue, state: BotLifecycleState, ran: bool = False) -> Bot:
    definition = BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"})
    return Bot(
        BotId("abc123"), definition, BotLifecycle(state, T0 if ran else None), T0
    )


@pytest.mark.parametrize("venue", _NOT_SPOT)
def test_a_futures_bot_says_only_a_spot_bot_changes_its_venue(
    venue: TradingVenue,
) -> None:
    bot = _bot(venue, BotLifecycleState.DRAFT)

    assert bot.venue_locked_reason == "Only a Spot bot can change its venue."


def test_the_venue_sentences_of_a_spot_bot_are_word_for_word() -> None:
    stopped = _bot(TradingVenue.SPOT_TESTNET, BotLifecycleState.STOPPED, ran=True)
    draft_that_ran = _bot(TradingVenue.SPOT_TESTNET, BotLifecycleState.DRAFT, ran=True)

    assert stopped.venue_locked_reason == (
        "A bot's venue is fixed once it has run; this one is stopped."
    )
    assert draft_that_ran.venue_locked_reason == (
        "A bot's venue is fixed once it has run."
    )


@pytest.mark.parametrize("target", [*_NOT_SPOT, TradingVenue.DISABLED])
def test_a_spot_draft_refuses_a_venue_that_is_not_spot_in_the_old_words(
    target: TradingVenue,
) -> None:
    bot = _bot(TradingVenue.SPOT_TESTNET, BotLifecycleState.DRAFT)

    with pytest.raises(BotVenueFixedError) as refused:
        bot.moved_to(target)

    assert str(refused.value) == f"{target.display_name} is not a Spot venue."


def test_the_planner_numbers_name_a_venue_that_trades_no_market_as_not_an_enabled_spot_venue() -> (
    None
):
    venue = TradingVenue.DISABLED

    said = read_planner_numbers(_NoVenueEnabled(), _CAPS, venue, "BTCUSDT")

    assert said == f"{venue.display_name} is not an enabled Spot venue"


@pytest.mark.parametrize("venue", _NOT_SPOT)
def test_the_planner_numbers_name_a_futures_venue_that_is_off_in_its_own_word(
    venue: TradingVenue,
) -> None:
    """`EPIC-039H`: bots run on Futures, so a Futures venue that is off is not called Spot."""
    said = read_planner_numbers(_NoVenueEnabled(), _CAPS, venue, "BTCUSDT")

    assert said == f"{venue.display_name} is not an enabled Futures venue"


def test_a_spot_venue_that_is_not_enabled_is_not_called_a_non_spot_venue() -> None:
    venue = TradingVenue.SPOT_TESTNET

    said = read_planner_numbers(_NoVenueEnabled(), _CAPS, venue, "BTCUSDT")

    assert said == f"{venue.display_name} is not an enabled Spot venue"


def test_the_run_facts_name_a_venue_the_app_does_not_trade_on() -> None:
    venue = TradingVenue.DISABLED

    facts = BotRunFactsReader(_NoVenueEnabled(), _CAPS).read(
        "abc123", venue, "BTCUSDT", {"lower": "1"}, ""
    )

    assert facts.venue_problem == (
        f"{venue.display_name} is not a Spot venue this app trades on"
    )


def test_a_futures_venue_that_is_off_says_not_enabled() -> None:
    """`EPIC-039H`: a Futures venue is one bots trade on, so only being off is its problem."""
    venue = TradingVenue.FUTURES_TESTNET
    facts = BotRunFactsReader(_NoVenueEnabled(), _CAPS).read(
        "abc123", venue, "BTCUSDT", {"lower": "1"}, ""
    )

    assert facts.venue_problem == f"{venue.display_name} is not enabled"


def test_futures_mainnet_that_is_off_says_not_enabled_like_every_futures_venue() -> (
    None
):
    """The owner opened it on 2026-10-17 (`EPIC-039L`): only being off is its problem."""
    venue = TradingVenue.FUTURES_MAINNET
    facts = BotRunFactsReader(_NoVenueEnabled(), _CAPS).read(
        "abc123", venue, "BTCUSDT", {"lower": "1"}, ""
    )

    assert facts.venue_problem == f"{venue.display_name} is not enabled"


def test_a_spot_venue_that_is_off_says_not_enabled() -> None:
    facts = BotRunFactsReader(_NoVenueEnabled(), _CAPS).read(
        "abc123", TradingVenue.SPOT_TESTNET, "BTCUSDT", {"lower": "1"}, ""
    )

    assert facts.venue_problem == "Spot Testnet is not enabled"
