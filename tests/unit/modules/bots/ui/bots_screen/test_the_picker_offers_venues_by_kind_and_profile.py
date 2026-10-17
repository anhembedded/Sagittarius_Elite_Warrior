"""`EPIC-039J` — which venues New bot and the Plan's Venue field list.

@details The business promise: a venue is listed when a kind declares its market, the build
lets bots run there, and the owner has opened it. Futures mainnet is listed like any
other venue since the owner opened it (`EPIC-039L`, O2; `BUG-208` listed it closed before); Spot's list is what it always was."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts import venue_profile
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_MARKETS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    NOT_ENABLED,
    venue_choices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_BOTH = frozenset({MarketType.SPOT, MarketType.FUTURES_USD_M})


class _NothingEnabled(IVenueContexts):
    def enabled(self) -> tuple[TradingVenue, ...]:
        return ()

    def get(self, venue: TradingVenue) -> VenueContext:
        raise AssertionError("a venue that is not enabled is not read")

    def primary(self) -> VenueContext:
        raise AssertionError("not used")


class _Kind(IBotKind):
    def __init__(self, markets: frozenset[MarketType]) -> None:
        self._markets = markets

    @property
    def kind_id(self) -> str:
        return "kind"

    def supported_profiles(self) -> frozenset[MarketType]:
        return self._markets

    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        raise AssertionError("not judged here")

    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        raise AssertionError("not drawn here")

    def executor_factory(self) -> IBotExecutorFactory:
        raise AssertionError("not run here")


def _listed(markets: frozenset[MarketType]) -> list[TradingVenue]:
    choices = venue_choices(_NothingEnabled(), [_Kind(markets)])
    assert {choice.connection for choice in choices} == {NOT_ENABLED}
    return [choice.venue for choice in choices]


@pytest.fixture
def futures_run_here(monkeypatch: pytest.MonkeyPatch) -> None:
    """The build-wide ceiling `EPIC-039H` raises, raised for the test."""
    monkeypatch.setattr(venue_profile, "BOT_MARKETS", _BOTH)


def test_a_spot_only_build_lists_the_two_spot_venues_as_it_always_did() -> None:
    assert _listed(SPOT_MARKETS) == [
        TradingVenue.SPOT_TESTNET,
        TradingVenue.SPOT_MAINNET,
    ]


def test_futures_testnet_is_listed_for_a_kind_that_declares_futures(
    futures_run_here: None,
) -> None:
    assert TradingVenue.FUTURES_TESTNET in _listed(_BOTH)


def test_futures_mainnet_is_listed_open_like_every_other_venue(
    futures_run_here: None,
) -> None:
    """The owner opened it on 2026-10-17 (`EPIC-039L`, decision O2): no venue is closed."""
    choices = {
        choice.venue: choice
        for choice in venue_choices(_NothingEnabled(), [_Kind(_BOTH)])
    }
    assert choices[TradingVenue.FUTURES_MAINNET].connection == NOT_ENABLED
    assert all(choice.closed_reason is None for choice in choices.values())


def test_a_kind_that_declares_only_spot_is_never_offered_a_futures_venue(
    futures_run_here: None,
) -> None:
    listed = _listed(SPOT_MARKETS)

    assert TradingVenue.FUTURES_TESTNET not in listed
    assert TradingVenue.SPOT_TESTNET in listed


def test_the_build_lets_bots_run_on_futures_so_a_kind_declaring_it_lists_its_testnet() -> (
    None
):
    """`EPIC-039H` raised the ceiling: a kind's declaration alone lists the Futures venues;
    Futures mainnet is listed, now it is open, in venue order."""
    assert _listed(_BOTH) == [
        TradingVenue.FUTURES_TESTNET,
        TradingVenue.SPOT_TESTNET,
        TradingVenue.FUTURES_MAINNET,
        TradingVenue.SPOT_MAINNET,
    ]
