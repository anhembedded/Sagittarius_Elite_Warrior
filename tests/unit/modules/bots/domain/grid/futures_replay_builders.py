"""Builders for the Futures replay tests (`EPIC-039K`): the report's worked example on a
position venue, a bracket table in the shape Binance publishes, and hand-built candles.

The brackets are illustrative (a four-tier table in the shape of `GET /fapi/v1/leverageBracket`),
not a recorded answer: nothing here asserts what Binance charges today."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.fine_klines import (
    FineKlinesByCandle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    FundingSchedule,
    FundingSettlement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_replay import (
    FuturesReplay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_run_terms import (
    FuturesRunTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

D = Decimal
START = datetime(2026, 9, 1, tzinfo=UTC)
MINUTE = timedelta(minutes=1)

#: Rates as fractions; the report's 0.1 % is Spot's, Futures' are lower.
MAKER = D("0.0002")
TAKER = D("0.0005")

BRACKETS = LeverageBrackets(
    "BTCUSDT",
    (
        LeverageBracket(1, 125, D(0), D(50_000), D("0.004"), D(0)),
        LeverageBracket(2, 100, D(50_000), D(250_000), D("0.005"), D(50)),
        LeverageBracket(3, 50, D(250_000), D(3_000_000), D("0.01"), D(1_300)),
        LeverageBracket(4, 20, D(3_000_000), D(15_000_000), D("0.025"), D(46_300)),
    ),
)


def position_config(
    direction: str, leverage: int = 5, **changes: str
) -> dict[str, str]:
    """The worked example as a position-venue definition: no stop or take profit unless a
    test asks, so a run ends by its data, a liquidation or what the test sets."""
    return {
        **CONFIG,
        "stop_loss": "off",
        "take_profit": "off",
        "direction": direction,
        "leverage": str(leverage),
        **changes,
    }


def settlement(
    minute: int, rate: str = "0.0001", mark: str | None = "65000"
) -> FundingSettlement:
    return FundingSettlement(
        START + timedelta(minutes=minute), D(rate), D(mark) if mark else None
    )


def schedule(*settlements: FundingSettlement) -> FundingSchedule:
    return FundingSchedule(settlements, True, f"{len(settlements)} settlements")


def charge(position: Decimal, mark: Decimal, rate: Decimal) -> Decimal:
    return position * mark * rate


def terms_of(funding: FundingSchedule | None = None) -> FuturesRunTerms:
    return FuturesRunTerms(BRACKETS, MAKER, TAKER, funding or schedule(), charge)


def bar(minute: int, o: str, h: str, low: str, c: str) -> PriceBar:
    return PriceBar(START + timedelta(minutes=minute), D(o), D(h), D(low), D(c))


def kline(minute: int, second: int, o: str, h: str, low: str, c: str) -> PriceBar:
    return PriceBar(
        START + timedelta(minutes=minute, seconds=second), D(o), D(h), D(low), D(c)
    )


def replay(
    bars: list[PriceBar],
    config: dict[str, str],
    funding: FundingSchedule | None = None,
    fine: dict[datetime, tuple[PriceBar, ...]] | None = None,
) -> GridBacktestResult:
    """`bars` replayed through the Futures engine under `config` (a position-venue
    definition), the way the application composes it."""
    params = GridParams.from_config(config)
    run = terms_of(funding)
    result = simulate_grid(
        GridBacktestInputs(
            params,
            TERMS,
            tuple(bars),
            MINUTE,
            FineKlinesByCandle(fine or {}),
            engine=lambda first: FuturesReplay(params, TERMS, run, first),
        )
    )
    assert isinstance(result, GridBacktestResult)
    return result
