"""`EPIC-039A` - what each venue allows, answered by one profile per market."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
    VenueTradesNoMarketError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    BOT_MARKETS,
    FUTURES_MARKETS,
    SPOT_LIMITS,
    SPOT_MARKETS,
    ExposureKind,
    ExposureLimits,
    bot_closed_reason,
    bot_profile_of,
    exposure_limits_of,
    is_offered,
    plan_limits_of,
    runs_bots_on,
    title_word_of,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
    GridKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_SPOT = (TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET)
_FUTURES = (TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET)


@pytest.mark.parametrize("venue", _SPOT, ids=lambda v: v.value)
def test_the_spot_profile_allows_long_only_with_no_leverage(
    venue: TradingVenue,
) -> None:
    profile = venue_profile_of(venue)

    assert profile is not None
    assert profile.market_type is MarketType.SPOT
    assert profile.directions == frozenset({TradeDirection.LONG})
    assert profile.margin_modes == frozenset(), "Spot has no margin mode"
    assert profile.has_funding is False
    assert profile.exposure_kind is ExposureKind.INVENTORY
    assert profile.needs_reduce_only_exits is False
    assert profile.title_word == "Spot"


@pytest.mark.parametrize("venue", _FUTURES, ids=lambda v: v.value)
def test_the_futures_profile_supports_every_direction_but_runs_long_for_now(
    venue: TradingVenue,
) -> None:
    profile = venue_profile_of(venue)

    assert profile is not None
    assert profile.market_type is MarketType.FUTURES_USD_M
    # The market supports all three, which a plan and a backtest may name; a bot runs LONG only
    # until `EPIC-039I` builds the short and neutral openings (`exposure_refusal` says so).
    assert profile.directions == frozenset(TradeDirection)
    assert profile.bot_directions == frozenset({TradeDirection.LONG})
    assert profile.margin_modes == frozenset({MarginMode.ISOLATED}), (
        "Cross is a later epic"
    )
    assert profile.has_funding is True
    assert profile.exposure_kind is ExposureKind.POSITION
    assert profile.needs_reduce_only_exits is True
    assert profile.title_word == "Futures"


def test_a_venue_that_trades_no_market_has_no_profile() -> None:
    assert venue_profile_of(TradingVenue.DISABLED) is None


def test_every_trading_venue_is_answered_and_the_two_markets_are_the_only_ones() -> (
    None
):
    markets = {
        profile.market_type
        for venue in TradingVenue
        if (profile := venue_profile_of(venue)) is not None
    }

    assert markets == {MarketType.SPOT, MarketType.FUTURES_USD_M}


def test_the_profile_is_a_value_nobody_can_change() -> None:
    profile = venue_profile_of(TradingVenue.SPOT_TESTNET)

    assert profile is not None
    with pytest.raises(AttributeError):
        profile.title_word = "Margin"  # type: ignore[misc]


def test_bots_run_on_spot_and_on_futures_in_this_build() -> None:
    """`EPIC-039H` flipped the build-wide ceiling together with the Grid's declaration."""
    spot = venue_profile_of(TradingVenue.SPOT_TESTNET)
    futures = venue_profile_of(TradingVenue.FUTURES_TESTNET)

    assert spot is not None and futures is not None
    assert runs_bots_on(spot) is True
    assert runs_bots_on(futures) is True
    assert BOT_MARKETS == SPOT_MARKETS | FUTURES_MARKETS
    assert frozenset({MarketType.FUTURES_USD_M}) == FUTURES_MARKETS


def test_a_kind_declaring_spot_only_is_refused_a_futures_venue() -> None:
    """The two switches are one rule: the market must be in the kind's set *and* in the
    build's. A kind that declares Spot only never gets a Futures venue, whatever the build
    allows; one that declares Futures gets it only while the build allows Futures."""
    for venue in _FUTURES:
        assert bot_profile_of(venue, SPOT_MARKETS) is None
        assert bot_profile_of(venue, FUTURES_MARKETS) is not None
        assert exposure_limits_of(venue, SPOT_MARKETS) == SPOT_LIMITS
    for venue in _SPOT:
        assert bot_profile_of(venue, FUTURES_MARKETS) is None
        assert bot_profile_of(venue, SPOT_MARKETS) is not None
    assert bot_profile_of(TradingVenue.DISABLED, GRID_MARKETS) is None


def test_the_injected_port_answers_what_the_function_does() -> None:
    profiles: IVenueProfiles = VenueProfilesByMarket()

    for venue in (*_SPOT, *_FUTURES):
        assert profiles.for_venue(venue) == venue_profile_of(venue)
    with pytest.raises(VenueTradesNoMarketError):
        profiles.for_venue(TradingVenue.DISABLED)


def test_every_kind_declares_the_markets_it_runs_on() -> None:
    """A kind states its markets on purpose (`IBotKind.supported_profiles`); one that says
    nothing, or a market no profile describes, fails here rather than in a venue picker."""
    kinds = [GridKind(None, GridThresholds())]  # type: ignore[arg-type]
    described = {
        profile.market_type
        for venue in TradingVenue
        if (profile := venue_profile_of(venue)) is not None
    }

    # A new production kind must join `kinds` above, so its declaration is checked.
    production = {
        sub
        for sub in IBotKind.__subclasses__()
        if sub.__module__.startswith("Sagittarius_Elite_Warrior.src")
    }
    assert production == {type(kind) for kind in kinds}
    for kind in kinds:
        supported = kind.supported_profiles()
        assert supported, kind.kind_id
        assert supported <= described, kind.kind_id


def test_the_profile_carries_the_highest_leverage_the_market_allows() -> None:
    """Spot has no leverage; Futures does (the symbol's bracket narrows it, `EPIC-039E`)."""
    for venue in _SPOT:
        assert venue_profile_of(venue).max_leverage == 1  # type: ignore[union-attr]
    for venue in _FUTURES:
        assert venue_profile_of(venue).max_leverage > 1  # type: ignore[union-attr]


def test_a_venue_bots_run_on_has_its_profiles_exposure_limits() -> None:
    for venue in _SPOT:
        assert (
            exposure_limits_of(venue, GRID_MARKETS)
            == SPOT_LIMITS
            == ExposureLimits(frozenset({TradeDirection.LONG}), 1)
        )
    for venue in _FUTURES:
        limits = exposure_limits_of(venue, GRID_MARKETS)
        assert limits.exposure_kind is ExposureKind.POSITION
        assert limits.max_leverage > 1
        assert limits.directions == frozenset({TradeDirection.LONG})


def test_a_plan_is_judged_on_what_the_market_allows_and_a_bot_on_what_it_runs() -> None:
    """`EPIC-039K` backtests and `EPIC-039J` plans a SHORT; a start refuses it until `EPIC-039I`."""
    for venue in _FUTURES:
        assert plan_limits_of(venue).directions == frozenset(TradeDirection)
        assert exposure_limits_of(venue, GRID_MARKETS).directions == frozenset(
            {TradeDirection.LONG}
        )
    for venue in _SPOT:
        assert plan_limits_of(venue) == exposure_limits_of(venue, GRID_MARKETS)


def test_futures_mainnet_alone_is_closed_to_bots_and_says_why() -> None:
    assert not is_offered(TradingVenue.FUTURES_MAINNET)
    assert is_offered(TradingVenue.FUTURES_TESTNET)
    assert "closed to bots" in (bot_closed_reason(TradingVenue.FUTURES_MAINNET) or "")
    for venue in (*_SPOT, TradingVenue.FUTURES_TESTNET, TradingVenue.DISABLED):
        assert bot_closed_reason(venue) is None


def test_a_venue_no_bot_runs_on_is_limited_as_spot_is() -> None:
    """Nothing is ever wider than Spot's for a venue the kind does not run on."""
    assert exposure_limits_of(TradingVenue.DISABLED, GRID_MARKETS) == SPOT_LIMITS
    for venue in _FUTURES:
        assert exposure_limits_of(venue, SPOT_MARKETS) == SPOT_LIMITS


def test_a_sentence_names_the_market_of_the_venue_it_is_about() -> None:
    """`EPIC-039J`: Spot's word is "Spot" as every sentence had it; a venue that trades no
    market is still described as Spot, so no existing sentence changed."""
    assert title_word_of(TradingVenue.SPOT_TESTNET) == "Spot"
    assert title_word_of(TradingVenue.SPOT_MAINNET) == "Spot"
    assert title_word_of(TradingVenue.FUTURES_TESTNET) == "Futures"
    assert title_word_of(TradingVenue.DISABLED) == "Spot"
