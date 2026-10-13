"""What a venue allows, decided here and nowhere else in `bots` (`EPIC-039A`, decision D1).

The Grid was Spot-only in fifteen places, each comparing `venue.market_type` with
`MarketType.SPOT`. Futures would have added a second `if` at each, and so would every kind
after the Grid. The comparison now lives in this one file: a site that needs to know what a
venue allows asks for its `VenueProfile` (`venue_profile_of`, or `IVenueProfiles` where a
port is injected), and `tests/unit/architecture/test_bots_decide_the_market_in_one_place.py`
fails on a new comparison anywhere else in `src/modules/bots/`.

@par Why a function as well as a port
The `Bot` aggregate (domain) must say whether its venue can change, and a domain entity
resolves no port. The table is a pure function over a value, so the entity can call it;
`VenueProfilesByMarket` (application) is the same answer behind `IVenueProfiles`, for the
sites that are injected and for a test that wants another table.

@par No `is_spot` and no `is_futures`
They would reinvite the branch this removes. What callers need is what the profile *says*:
the directions, the margin modes, whether there is funding, whether the exposure is an
inventory or a position, and the word to show the user.

@par Extension cases
  · Cross margin - add `MarginMode.CROSS` to the Futures profile's `margin_modes`;
  · a market (Coin-M, delivery) - one more `VenueProfile`, one more arm of `venue_profile_of`,
    and its markets in the kinds that support it;
  · a second exchange - the profile becomes keyed by venue instead of market; the sites do
    not change, because they ask for the profile.
Two switches, one rule. `BOT_MARKETS` is the build-wide ceiling and the only one read today:
a venue is one bots run on only when its market is in it. `IBotKind.supported_profiles` is
each kind's own declaration and is read from `EPIC-039H`, which makes the rule "the market is
in the kind's set *and* in `BOT_MARKETS`". Until `039H` flips both for the Grid, Futures
*exists* here and no bot runs on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SPOT_TITLE = "Spot"
FUTURES_TITLE = "Futures"


class ExposureKind(str, Enum):
    #: What a bot holds is an inventory of the base asset, derived from its tagged fills.
    INVENTORY = "inventory"
    #: What a bot holds is a signed position (`EPIC-039D`).
    POSITION = "position"


@dataclass(frozen=True, slots=True)
class VenueProfile:
    market_type: MarketType
    directions: frozenset[TradeDirection]
    margin_modes: frozenset[MarginMode]
    has_funding: bool
    exposure_kind: ExposureKind
    needs_reduce_only_exits: bool
    #: The word the user reads for this market ("Spot", "Futures").
    title_word: str
    #: The highest leverage a bot may name on this market: 1 where there is none. A symbol's
    #: bracket narrows it further (`EPIC-039E`).
    max_leverage: int = 1


#: Binance USD-M's highest leverage on any symbol; each symbol's bracket allows less.
_FUTURES_MAX_LEVERAGE = 125

_SPOT = VenueProfile(
    market_type=MarketType.SPOT,
    directions=frozenset({TradeDirection.LONG}),
    margin_modes=frozenset(),
    has_funding=False,
    exposure_kind=ExposureKind.INVENTORY,
    needs_reduce_only_exits=False,
    title_word=SPOT_TITLE,
)

_FUTURES = VenueProfile(
    market_type=MarketType.FUTURES_USD_M,
    directions=frozenset(TradeDirection),
    margin_modes=frozenset({MarginMode.ISOLATED}),
    has_funding=True,
    exposure_kind=ExposureKind.POSITION,
    needs_reduce_only_exits=True,
    title_word=FUTURES_TITLE,
    max_leverage=_FUTURES_MAX_LEVERAGE,
)

#: The markets of the Spot profile: what a kind that supports Spot declares.
SPOT_MARKETS: frozenset[MarketType] = frozenset({MarketType.SPOT})

#: The markets a bot may run on **today**, the build-wide ceiling `EPIC-039H` raises to add
#: Futures together with the Grid kind's `supported_profiles` (the per-kind half of the rule). A venue whose profile is outside it is "not a venue bots trade
#: on yet", whatever its profile allows.
BOT_MARKETS: frozenset[MarketType] = SPOT_MARKETS


def venue_profile_of(venue: TradingVenue) -> VenueProfile | None:
    """The profile of `venue`'s market, or `None` for a venue that trades no market.

    This is the only place in `bots` that reads `venue.market_type` to decide behaviour.
    """
    market = venue.market_type
    if market is MarketType.SPOT:
        return _SPOT
    if market is MarketType.FUTURES_USD_M:
        return _FUTURES
    return None


def title_word_of(venue: TradingVenue) -> str:
    """The word the user reads for `venue`'s market in a sentence: "Spot" or "Futures". A
    venue that trades no market is described as Spot, as every sentence did before Futures."""
    profile = venue_profile_of(venue)
    return profile.title_word if profile is not None else SPOT_TITLE


def is_in_markets(profile: VenueProfile, markets: frozenset[MarketType]) -> bool:
    """Whether the profile's market is one of `markets`: a kind's declared set, or its
    backtest's."""
    return profile.market_type in markets


def runs_bots_on(profile: VenueProfile) -> bool:
    """Whether a bot can run on this profile's market in this build."""
    return is_in_markets(profile, BOT_MARKETS)


@dataclass(frozen=True, slots=True)
class ExposureLimits:
    """What a bot's parameters may ask of its venue: the directions and the leverage."""

    directions: frozenset[TradeDirection]
    max_leverage: int


#: The Spot profile's limits: LONG at 1. What a kind judges against when no venue speaks.
SPOT_LIMITS = ExposureLimits(_SPOT.directions, _SPOT.max_leverage)


def exposure_limits_of(venue: TradingVenue) -> ExposureLimits:
    """The limits of a venue bots run on; Spot's for any other, so nothing is ever wider."""
    profile = bot_profile_of(venue)
    if profile is None:
        return SPOT_LIMITS
    return ExposureLimits(profile.directions, profile.max_leverage)


#: Venues a bot runs on in this build but that the picker does not offer yet. Futures mainnet
#: is closed until the owner opens it: a protective stop for every position and the owner's
#: 14-day Futures-testnet soak come first (`EPIC-039` decision O7, delivered by `EPIC-039L`,
#: which replaces this set by the gate it builds). A bot already on such a venue is not moved.
CLOSED_VENUES: frozenset[TradingVenue] = frozenset({TradingVenue.FUTURES_MAINNET})


def is_offered(venue: TradingVenue) -> bool:
    """Whether the New bot and Venue pickers list `venue`: a venue bots run on, not closed."""
    return bot_profile_of(venue) is not None and venue not in CLOSED_VENUES


def bot_profile_of(venue: TradingVenue) -> VenueProfile | None:
    """The profile of a venue a bot can run on in this build, else `None`."""
    profile = venue_profile_of(venue)
    return profile if profile is not None and runs_bots_on(profile) else None


#: The market a bot reads data for where no venue is at hand (a symbol list, a tick feed, a
#: chart default). It is the Grid's market today; `EPIC-039H` makes those sites ask a venue.
BOT_MARKET: MarketType = MarketType.SPOT


def market_of(venue: TradingVenue) -> MarketType:
    """The market to read data for on behalf of a bot on `venue`.

    Callers refuse a venue bots do not run on before they read, so the fallback to
    `BOT_MARKET` is only the unreachable branch, not a decision.
    """
    profile = bot_profile_of(venue)
    return profile.market_type if profile is not None else BOT_MARKET
