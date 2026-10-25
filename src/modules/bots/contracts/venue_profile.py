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
Two switches, one rule (`EPIC-039H` flipped both for the Grid). `BOT_MARKETS` is the
build-wide ceiling; `IBotKind.supported_profiles` is each kind's own declaration. A venue is
one a kind's bots run on only when its market is in the kind's set *and* in `BOT_MARKETS`
(`bot_profile_of(venue, supported)`), so a kind that declares Spot only is never given a
Futures venue, whatever the build allows.

No venue is closed to bots today: Futures mainnet was closed by `CLOSED_VENUES` until the owner
opened it on 2026-10-17 (`EPIC-039L`, decision O2). What stands in front of real money on a
mainnet venue is the confirmation the start or resume carries (`TradingVenue.is_mainnet`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    COMMON_LAYER,
    PAUSE_RULE,
    PRICE_FEED_STALE,
    RATE_LIMITED,
    EffectivePolicy,
    RecoveryLayer,
    RuleChange,
    effective_policy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The venue layer that says nothing: the common set and the kind's stand.
NO_VENUE_RECOVERY = RecoveryLayer("venue")

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
    #: The directions a bot may **run** today, a subset of `directions` (what the market supports,
    #: which a plan and a backtest may name). Futures runs all three (`EPIC-039I`). The start's preconditions and the readiness refuse a direction outside
    #: the set in one sentence (`exposure_refusal`).
    bot_directions: frozenset[TradeDirection] = frozenset({TradeDirection.LONG})
    #: What a stopped bot is left holding, in the user's word: "base" for an inventory, "position"
    #: for a signed position (`BUG-219`; a Short is bought back, never "sold").
    held_word: str = "base"
    #: The Stop choice that ends the exposure at market, worded for `held_word`.
    close_at_market_label: str = "Sell the base at market"
    #: Which halts recover by themselves on this market (`EPIC-042`, ADR 042 §2.3): the venue
    #: layer of the policy, folded last. Empty keeps the common set and the kind's.
    recovery_layer: RecoveryLayer = NO_VENUE_RECOVERY


#: Binance USD-M's highest leverage on any symbol; each symbol's bracket allows less.
_FUTURES_MAX_LEVERAGE = 125

SPOT_PROFILE = VenueProfile(
    market_type=MarketType.SPOT,
    directions=frozenset({TradeDirection.LONG}),
    margin_modes=frozenset(),
    has_funding=False,
    exposure_kind=ExposureKind.INVENTORY,
    needs_reduce_only_exits=False,
    title_word=SPOT_TITLE,
    recovery_layer=RecoveryLayer("spot"),
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
    bot_directions=frozenset(TradeDirection),
    held_word="position",
    close_at_market_label="Close the position at market",
    # Its halt closes the position and EPIC-039L governs it: it clears every lower layer, so a
    # down stream and whatever a kind adds are not recovered by itself. It lists two exceptions.
    # The exchange's pause halts nothing and closes nothing, and a Futures bot always resumed from
    # it by itself (`BUG-216`, `EPIC-042F`). A quiet price feed is waited out under the default
    # rule, but the halt is a wait only while a stop on the exchange covers the position; the
    # halt asks (`GridCoveredWait`), and any other answer is the plain halt that closes
    # (`BUG-270`). Opening Futures to more reasons later deletes `clears_lower_layers` (ADR 042 D5).
    recovery_layer=RecoveryLayer(
        "futures",
        clears_lower_layers=True,
        changes={RATE_LIMITED: PAUSE_RULE, PRICE_FEED_STALE: RuleChange()},
    ),
)

#: The markets of the Spot profile: what a kind that supports Spot declares.
SPOT_MARKETS: frozenset[MarketType] = frozenset({MarketType.SPOT})

#: The markets of the USDⓈ-M Futures profile (decision D4): what a kind that supports Futures declares.
FUTURES_MARKETS: frozenset[MarketType] = frozenset({MarketType.FUTURES_USD_M})

#: Every market a profile exists for: what a kind that supports both declares.
PROFILE_MARKETS: frozenset[MarketType] = SPOT_MARKETS | FUTURES_MARKETS

#: The markets a bot may run on in this build, the build-wide ceiling (`EPIC-039H` raised it to
#: Futures together with the Grid kind's `supported_profiles`, the per-kind half of the rule).
#: A venue whose profile is outside it is "not a venue bots trade on", whatever its profile allows.
BOT_MARKETS: frozenset[MarketType] = SPOT_MARKETS | FUTURES_MARKETS


def venue_profile_of(venue: TradingVenue) -> VenueProfile | None:
    """The profile of `venue`'s market, or `None` for a venue that trades no market.

    This is the only place in `bots` that reads `venue.market_type` to decide behaviour.
    """
    market = venue.market_type
    if market is MarketType.SPOT:
        return SPOT_PROFILE
    if market is MarketType.FUTURES_USD_M:
        return _FUTURES
    return None


#: The venue layer of a venue that trades no market: nothing recovers by itself there.
_UNKNOWN_VENUE_RECOVERY = RecoveryLayer("unknown venue", clears_lower_layers=True)


def recovery_policy_of(
    kind_layer: RecoveryLayer, venue: TradingVenue
) -> EffectivePolicy:
    """The halt-recovery policy of a bot of a kind with `kind_layer` on `venue` (`EPIC-042C`):
    the common, kind and venue layers merged (`effective_policy`, ADR 042 §2.3). The one place a
    bot's policy is resolved; the director, `bot show` and the generated table all read it."""
    profile = venue_profile_of(venue)
    venue_layer = profile.recovery_layer if profile else _UNKNOWN_VENUE_RECOVERY
    return effective_policy(COMMON_LAYER, kind_layer, venue_layer)


def title_word_of(venue: TradingVenue) -> str:
    """The word the user reads for `venue`'s market in a sentence: "Spot" or "Futures". A
    venue that trades no market is described as Spot, as every sentence did before Futures."""
    profile = venue_profile_of(venue)
    return profile.title_word if profile is not None else SPOT_TITLE


def keep_on_stop_closed_reason(profile: VenueProfile) -> str | None:
    """Why a bot on `profile`'s market cannot be stopped with what it holds kept, or `None` when
    it can (`EPIC-039H`, decision O8). The Stop dialog disables "keep" with this sentence and the
    Stop use case refuses it by the same test (`BUG-219`), so the two cannot disagree."""
    if profile.exposure_kind is not ExposureKind.POSITION:
        return None
    return "needs a stop on the exchange, EPIC-039L"


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
    #: What the venue's bot holds: an inventory or a position. A kind sizes its levels by it
    #: (`EPIC-039B`: a position is only a function of price when every level has the same
    #: quantity).
    exposure_kind: ExposureKind = ExposureKind.INVENTORY


#: The Spot profile's limits: LONG at 1. What a kind judges against when no venue speaks.
SPOT_LIMITS = ExposureLimits(
    SPOT_PROFILE.directions, SPOT_PROFILE.max_leverage, SPOT_PROFILE.exposure_kind
)


def exposure_limits_of(
    venue: TradingVenue, supported: frozenset[MarketType]
) -> ExposureLimits:
    """The limits of a venue a kind that supports `supported` runs on; Spot's for any other,
    so nothing is ever wider."""
    profile = bot_profile_of(venue, supported)
    if profile is None:
        return SPOT_LIMITS
    return ExposureLimits(
        profile.bot_directions, profile.max_leverage, profile.exposure_kind
    )


def bot_profile_of(
    venue: TradingVenue, supported: frozenset[MarketType]
) -> VenueProfile | None:
    """The profile of a venue a bot of a kind declaring `supported` markets can run on, else
    `None`: the market must be in the kind's set and in this build's (`BOT_MARKETS`)."""
    profile = venue_profile_of(venue)
    if profile is None or profile.market_type not in supported:
        return None
    return profile if runs_bots_on(profile) else None


def direction_closed_reason(
    profile: VenueProfile, direction: TradeDirection
) -> str | None:
    """Why a bot cannot run `direction` on `profile`'s market yet, or `None` when it can (or the
    market does not offer it at all). A direction a plan and a backtest may name before a bot may
    run it is shown greyed out with this sentence, never selectable and then refused at Start
    (`EPIC-039I`)."""
    if direction not in profile.directions or direction in profile.bot_directions:
        return None
    return (
        f"A {direction.value} grid cannot run on {profile.title_word} yet; a plan and a "
        "backtest may name it."
    )


def plan_limits_of(venue: TradingVenue) -> ExposureLimits:
    """The limits of `venue`'s market whether or not a bot may run there yet; Spot's for a venue
    that trades no market.

    @details A backtest replays a plan, it starts nothing, so it is judged against what the
    market allows (`EPIC-039K`), where `exposure_limits_of` answers what a bot may start with
    in this build."""
    profile = venue_profile_of(venue)
    if profile is None:
        return SPOT_LIMITS
    return ExposureLimits(
        profile.directions, profile.max_leverage, profile.exposure_kind
    )


def plan_market_of(venue: TradingVenue) -> MarketType:
    """The market a plan on `venue` is read and replayed on, whether or not a bot may run
    there yet (`EPIC-039K`); `market_of` is the market a running bot trades."""
    profile = venue_profile_of(venue)
    return profile.market_type if profile is not None else BOT_MARKET


#: The market a bot reads data for where no venue is at hand (a symbol list, a tick feed, a
#: chart default). It is the Grid's market today; `EPIC-039H` makes those sites ask a venue.
BOT_MARKET: MarketType = MarketType.SPOT


def market_of(
    venue: TradingVenue, supported: frozenset[MarketType] = PROFILE_MARKETS
) -> MarketType:
    """The market to read data for on behalf of a bot of a kind declaring `supported` on `venue`
    (any kind, for a screen that has none in hand).

    Callers refuse a venue bots do not run on before they read, so the fallback to
    `BOT_MARKET` is only the unreachable branch, not a decision.
    """
    profile = bot_profile_of(venue, supported)
    return profile.market_type if profile is not None else BOT_MARKET
