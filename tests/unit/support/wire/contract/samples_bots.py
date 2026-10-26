"""`EPIC-047A` — a full and a minimal instance of the bots contracts the link carries.

See `samples_trading.py` for what *full* and *minimal* mean.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills.result import (
    BotFill,
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market.result import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.result import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessAdvisory,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.connection_read import (
    ConnectionRead,
    ConnectionState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeFacts,
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    RefusedBotFile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_risk_read import (
    PlanRiskUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import (
    BotRunFacts,
    RunFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    ExchangeTerms,
    FundingView,
    MarketView,
    PlanRiskFacts,
    PriceBand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import PnlSummary
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    HaltCode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    RecoveryAttempt,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_trading import (
    BANGKOK,
    UTC_NOON,
    full_brackets,
    full_budget_caps,
    full_connect_failure,
    full_earlier_runs,
    full_symbol_setting,
    minimal_brackets,
    minimal_budget_caps,
    minimal_connect_failure,
    minimal_earlier_runs,
)

D = Decimal


def full_pnl() -> PnlSummary:
    return PnlSummary(
        D("12.3400"), D("10"), D("2.34"), D("11.1"), D("-0.5"), 2, D("0.05"), D("-0.01")
    )


def minimal_pnl() -> PnlSummary:
    return PnlSummary(None, D(0), None, D(0), None, 0)


def full_progress() -> BotProgress:
    return BotProgress(
        realised_profit=D("10.10"),
        completed_cycles=3,
        open_orders=2,
        inventory=D("0.00500000"),
        average_cost=D("67000.1"),
        reason="TAKE_PROFIT",
        reason_detail="the price reached the take profit",
        orders=(
            BotOrderLine(
                1,
                "BUY",
                D("66000.5"),
                D("0.001"),
                D("0.0005"),
                "sew-1-b1",
                "PARTIALLY_FILLED",
            ),
            BotOrderLine(2, "SELL", D("68000"), D("0.001"), D(0), "sew-1-s2"),
        ),
        mark_price=D("67010.5"),
        earlier_runs_base=D("0.1"),
        earlier_runs_cost=D("6000.5"),
        cost=D("335.0005"),
        pnl=full_pnl(),
        mark_price_at=BANGKOK,
        maker_fee=D("0.001"),
    )


def minimal_progress() -> BotProgress:
    return BotProgress(
        realised_profit=D(0),
        completed_cycles=0,
        open_orders=0,
        inventory=D(0),
        average_cost=None,
        reason="",
        reason_detail="",
    )


def full_bot() -> BotSnapshot:
    return BotSnapshot(
        bot_id="b-0001",
        name="BTC grid",
        kind="grid",
        venue=TradingVenue.FUTURES_TESTNET,
        symbol="BTCUSDT",
        state=BotLifecycleState.RECOVERING,
        created_at=BANGKOK,
        run_started_at=UTC_NOON,
        config={"lower": "60000.00", "upper": "70000", "levels": "10"},
        progress=full_progress(),
        venue_locked="a run holds orders on it",
        recovering_from=BotLifecycleState.RUNNING,
        recovery_attempts=(
            RecoveryAttempt(HaltCode("stream-lost"), BANGKOK),
            RecoveryAttempt(HaltCode("clock-gap"), UTC_NOON),
        ),
    )


def minimal_bot() -> BotSnapshot:
    return BotSnapshot(
        bot_id="b-0002",
        name="draft",
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="ETHUSDT",
        state=BotLifecycleState.DRAFT,
        created_at=UTC_NOON,
        run_started_at=None,
    )


def full_bot_list() -> BotList:
    return BotList(
        (full_bot(), minimal_bot()), (RefusedBotFile("b-0003.json", "unreadable"),)
    )


def minimal_bot_list() -> BotList:
    return BotList()


def full_fills() -> BotFills:
    return BotFills(
        (
            BotFill(BANGKOK, "BUY", D("66000.50"), D("0.00100000"), "sew-1-b1"),
            BotFill(UTC_NOON, "SELL", None, D("0.001"), "sew-1-s2"),
        ),
        "some fills not read",
        True,
        full_connect_failure(),
    )


def minimal_fills() -> BotFills:
    return BotFills()


def full_fills_refused() -> BotFills:
    return BotFills(refused=minimal_connect_failure())


def full_readiness() -> BotReadiness:
    item = ReadinessItem(
        ReadinessStep.DESIGN,
        "range",
        "the lower limit is above the price",
        ReadinessFix.EDIT_FIELD,
        BotRefusal.PARAMETERS_REFUSED,
        "lower",
    )
    return BotReadiness(
        (
            StepReadiness(ReadinessStep.CONNECT, StepStatus.DONE),
            StepReadiness(ReadinessStep.DESIGN, StepStatus.OPEN, (item,)),
            StepReadiness(ReadinessStep.RUN, StepStatus.WAITING),
        ),
        (
            ReadinessAdvisory(
                "wide-range", "the range is wider than a week of movement"
            ),
        ),
    )


def minimal_readiness() -> BotReadiness:
    return BotReadiness((StepReadiness(ReadinessStep.CONNECT, StepStatus.DONE),))


def full_run_facts() -> BotRunFacts:
    return BotRunFacts(
        RunFacts(
            "the venue is not ready",
            "b-0009",
            ("b-0010", "b-0011"),
            ("b-0012",),
            "b-0013",
            "the budget allows 20 open orders",
        ),
        full_budget_caps(),
    )


def minimal_run_facts() -> BotRunFacts:
    return BotRunFacts(RunFacts(), minimal_budget_caps())


def full_command_result() -> BotCommandResult:
    return BotCommandResult(
        False, "b-0001", BotRefusal.SYMBOL_LEASED, "BTCUSDT is leased by b-0009"
    )


def minimal_command_result() -> BotCommandResult:
    return BotCommandResult(True)


def full_exchange_facts() -> ExchangeFacts:
    return ExchangeFacts(
        venue_title="Spot testnet",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        read_at=BANGKOK,
        base_free=D("0.1"),
        base_locked=D("0.2"),
        quote_free=D("1000.10"),
        quote_locked=D("5"),
        own_sell_base=D("0.05"),
        own_buy_quote=D("2.5"),
        own_open_orders=3,
        foreign_open_orders=1,
        earlier_runs=full_earlier_runs(),
        can_trade=True,
    )


def minimal_exchange_facts() -> ExchangeFacts:
    return ExchangeFacts(
        "Spot testnet", "ETHUSDT", "ETH", "USDT", UTC_NOON, D(0), D(0), D(0), D(0), D(0), D(0), 0, 0,
        minimal_earlier_runs(), None,
    )  # fmt: skip


def full_futures_facts() -> FuturesFacts:
    return FuturesFacts(
        "Futures testnet", "BTCUSDT", "USDT", BANGKOK, D("900.5"), D("-0.002"), PositionMode.HEDGE,
        full_symbol_setting(), full_brackets(), 2, 1, True, AssetMode.MULTI_ASSETS,
    )  # fmt: skip


def minimal_futures_facts() -> FuturesFacts:
    return FuturesFacts(
        "Futures testnet", "ETHUSDT", "USDT", UTC_NOON, D(0), D(0), PositionMode.ONE_WAY,
        full_symbol_setting(), minimal_brackets(), 0, 0, None,
    )  # fmt: skip


def full_plan_risk() -> PlanRiskFacts:
    return PlanRiskFacts(full_symbol_setting(), full_brackets())


def full_planner_market() -> PlannerMarket:
    return PlannerMarket(
        ExchangeTerms(
            D("0.01"), D("0.00001"), D("5"), D("0.001"), D("0.00075"), D("9000000"), 200,
            D("0.00002"), PriceBand(D("0.2"), D("5"), D("0.2"), D("5")), "TRADING",
        ),
        MarketView(D("67000.5"), D("1500.25"), 2, FundingView(D("0.0001")), "BTC", "USDT", ""),
        SuggestedRange(D("60000"), D("70000")),
        SuggestedRange(D("61000.5"), D("69000.5")),
        "",
    )  # fmt: skip


def minimal_planner_market() -> PlannerMarket:
    return PlannerMarket(None, None, None, None, "the venue is not enabled")


def minimal_planner_market_unpriced() -> PlannerMarket:
    return PlannerMarket(
        ExchangeTerms(D(1), D(1), D(1), D(0), D(0), D(1), 1),
        MarketView(D(1), None, None, FundingView(None)),
        None,
        None,
    )


def full_connection() -> ConnectionRead:
    return ConnectionRead(
        ConnectionState.CONNECTED,
        "Spot testnet",
        AccountView(D("1000.10"), "USDT", True, "Spot testnet"),
        "",
    )


def minimal_connection() -> ConnectionRead:
    return ConnectionRead(ConnectionState.READING, "Spot testnet")


def unavailable_plan_risk() -> PlanRiskUnavailable:
    return PlanRiskUnavailable("the venue has no position risk")


def checking() -> ExchangeChecking:
    return ExchangeChecking()


def unavailable() -> ExchangeUnavailable:
    return ExchangeUnavailable("the exchange did not answer")


def loaded_exchange_full() -> ExchangeLoaded:
    return ExchangeLoaded(full_exchange_facts())


def loaded_exchange_minimal() -> ExchangeLoaded:
    return ExchangeLoaded(minimal_exchange_facts())


def loaded_futures_full() -> FuturesLoaded:
    return FuturesLoaded(full_futures_facts())


def loaded_futures_minimal() -> FuturesLoaded:
    return FuturesLoaded(minimal_futures_facts())
