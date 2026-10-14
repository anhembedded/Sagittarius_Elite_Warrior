"""`EPIC-039H` - a Futures bot is judged by the Futures rules, against the plan the executor draws.

@details `assess_readiness` is the one function the screen and Start call. For a position venue
it reads the venue profile: the exchange's facts are a `FuturesSnapshot`, what the plan asks of the
account is `FuturesNeeds` (the worst-case notional of the ladder, the initial margin it reserves at
the bot's leverage), and the kind judges the parameters against the venue's limits. A Spot bot is
judged as it always was; the Spot suites pin that.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.futures_ladder_needs import (
    resume_futures_needs,
    start_futures_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.readiness_assessment import (
    ConnectionRead,
    ConnectionState,
    ReadinessInputs,
    RunFacts,
    assess_readiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.exchange_rules import (
    RunPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_rules import (
    FOREIGN_POSITION,
    MARGIN_SHORT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_needs import (
    resume_needs_of,
    start_needs_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
    bot_profile_of,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_needs import (
    FuturesNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
    GridKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_needs import (
    LadderNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    AVAILABLE_MARGIN,
    BRACKETS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

D = Decimal
_FUTURES = venue_profile_of(TradingVenue.FUTURES_TESTNET)
_SPOT = venue_profile_of(TradingVenue.SPOT_TESTNET)
_KIND = GridKind(None, GridThresholds())  # type: ignore[arg-type]
_TITLE = "Futures Testnet"
#: A long at 3x on the report's 60,000 to 70,000 range, with an exit below it (decision O3).
_LONG = {**CONFIG, "direction": "LONG", "leverage": "3", "stop_loss": "price:50000"}
_LIMITS = ExposureLimits(frozenset({TradeDirection.LONG}), 125, ExposureKind.POSITION)
_MARKET = PlannerMarket(TERMS, MarketView(LAST_PRICE), None, None)
_CONNECTED = ConnectionRead(
    ConnectionState.CONNECTED,
    _TITLE,
    AccountView(AVAILABLE_MARGIN, "USDT", True, _TITLE),
)


def _facts(**changes: object) -> FuturesLoaded:
    base = FuturesFacts(
        venue_title=_TITLE,
        symbol="BTCUSDT",
        quote_asset="USDT",
        read_at=datetime(2026, 10, 13, 9, tzinfo=UTC),
        available_margin=AVAILABLE_MARGIN,
        position=D(0),
        position_mode=PositionMode.ONE_WAY,
        symbol_setting=FuturesSymbolSetting(
            "BTCUSDT", 3, MarginType.ISOLATED, D(1_000_000)
        ),
        brackets=BRACKETS,
        own_open_orders=0,
        foreign_open_orders=0,
        can_trade=True,
    )
    return FuturesLoaded(replace(base, **changes))  # type: ignore[arg-type]


def _assess(exchange: FuturesLoaded, config: dict[str, str] | None = None):
    assert _FUTURES is not None
    return assess_readiness(
        ReadinessInputs(
            kind=_KIND,
            kind_id="grid",
            symbol="BTCUSDT",
            config=config or _LONG,
            connection=_CONNECTED,
            market=_MARKET,
            run=RunFacts(),
            exchange=exchange,
            profile=_FUTURES,
            limits=_LIMITS,
        )
    )


def test_a_futures_profile_is_chosen_by_the_grids_declaration_and_the_build() -> None:
    assert bot_profile_of(TradingVenue.FUTURES_TESTNET, GRID_MARKETS) == _FUTURES
    assert _FUTURES is not None and _FUTURES.exposure_kind is ExposureKind.POSITION


def test_a_start_needs_the_margin_of_the_ladders_worst_case_at_the_bots_leverage() -> (
    None
):
    assert _FUTURES is not None
    needs = start_needs_of(_FUTURES, _LONG, TERMS, LAST_PRICE)

    assert isinstance(needs, FuturesNeeds)
    assert needs.leverage == 3
    assert needs.initial_margin == needs.worst_case_notional / 3
    assert needs.worst_case_notional <= D(10_000) * 3, "within the capital reached"


def test_a_spot_start_needs_quote_and_base_as_it_always_did() -> None:
    assert _SPOT is not None

    assert isinstance(start_needs_of(_SPOT, CONFIG, TERMS, LAST_PRICE), LadderNeeds)


def test_a_resume_needs_the_notional_of_what_is_held_and_what_the_buys_add() -> None:
    assert _FUTURES is not None
    held = OwnerInventory(D("0.05"), D("0.05") * LAST_PRICE)

    needs = resume_needs_of(_FUTURES, _LONG, TERMS, LAST_PRICE, held)

    assert isinstance(needs, FuturesNeeds)
    assert needs.worst_case_notional >= held.cost
    assert needs == resume_futures_needs(_LONG, TERMS, LAST_PRICE, held)


def test_unreadable_parameters_draw_no_needs() -> None:
    assert start_futures_needs({"lower": "oops"}, TERMS, LAST_PRICE) is None


def test_a_sound_futures_plan_on_a_funded_flat_account_leaves_nothing() -> None:
    readiness = _assess(_facts())

    assert readiness.can_start, readiness.message()


def test_a_futures_account_with_too_little_margin_is_told_so_in_the_futures_words() -> (
    None
):
    readiness = _assess(_facts(available_margin=D(50)))

    assert [item.code for item in readiness.items] == [MARGIN_SHORT]


def test_a_position_that_stands_is_a_futures_item_not_a_spot_balance() -> None:
    readiness = _assess(_facts(position=D("0.01")))

    assert [item.code for item in readiness.items] == [FOREIGN_POSITION]
    assert "already holds a long position" in readiness.items[0].reason


def test_a_short_plan_is_refused_by_the_one_sentence_of_the_venues_limits() -> None:
    readiness = _assess(_facts(), {**_LONG, "direction": "SHORT"})

    assert [item.code for item in readiness.items] == ["DIRECTION_NOT_ALLOWED"]
    assert RunPurpose.START is not RunPurpose.RESUME
