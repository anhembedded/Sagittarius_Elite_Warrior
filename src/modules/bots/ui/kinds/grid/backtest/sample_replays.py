"""`EPIC-040F` — the Grid's sample replays, offline, for the workbench's frames and the tests that need a
real result to read.

The report's example (BTC around 65,000, 60,000–70,000, 10 grids, exits 5% beyond it) replayed on five
days of hourly sample candles, coarse (no 1-second klines), so the figures show that caveat too; and a
Long grid at 5x replayed over minute candles through the Futures engine, with or without a crash through
its liquidation price. Each replay runs here through `simulate_grid`, not the query; nothing opens a
socket or starts a pool.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.streamed_fine_klines import (
    price_bar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.preview_ports import (
    SAMPLE_CANDLES,
    sample_candle,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)

SYMBOL = "BTCUSDT"
INTERVAL = TimeFrame.ONE_HOUR
START = datetime(2026, 9, 28, tzinfo=UTC)
CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "10000",
    "stop_loss": "percent:5",
    "take_profit": "percent:5",
}
TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)
BRACKETS = LeverageBrackets(
    SYMBOL,
    (
        LeverageBracket(
            1, 125, Decimal(0), Decimal(50_000), Decimal("0.004"), Decimal(0)
        ),
    ),
)
_MAKER = Decimal("0.0002")
_TAKER = Decimal("0.0005")
_FUNDING_DOWN = "The exchange could not be reached."


def funding_refusal(reason: str = _FUNDING_DOWN) -> GridBacktestRefusal:
    """What the query answers when a Futures period's funding cannot be read
    (`futures_preparation._without_history`); a unit test holds it equal to the real one. It is
    canned because the real answer needs a Futures store and a failing funding history."""
    return GridBacktestRefusal(
        f"{reason} A Futures backtest without funding flatters a leveraged "
        "grid, so none was run.",
        funding_unavailable=True,
    )


def sample_result() -> GridBacktestResult:
    """The Spot example over five days of hourly sample candles."""
    bars = tuple(
        price_bar(sample_candle(SYMBOL, INTERVAL, START, index))
        for index in range(SAMPLE_CANDLES)
    )
    replay = simulate_grid(
        GridBacktestInputs(
            GridParams.from_config(CONFIG),
            TERMS,
            bars,
            timedelta(seconds=INTERVAL.to_seconds()),
        )
    )
    if not isinstance(replay, GridBacktestResult):
        raise TypeError("the sample replay was cancelled")
    return replay


def _bar(minute: int, prices: tuple[str, str, str, str]) -> PriceBar:
    """One candle: its minute and its open, high, low and close."""
    o, h, low, c = (Decimal(price) for price in prices)
    return PriceBar(START + timedelta(minutes=minute), o, h, low, c)


def _futures_replay(
    config: Mapping[str, str], bars: tuple[PriceBar, ...], note: str
) -> GridBacktestResult:
    """The same engine the application composes for a position venue."""
    params = GridParams.from_config(config)
    funding = FundingSchedule(
        (FundingSettlement(START + timedelta(minutes=2), Decimal("0.0001"), None),),
        True,
        note,
    )
    run = FuturesRunTerms(
        BRACKETS,
        _MAKER,
        _TAKER,
        funding,
        lambda position, mark, rate: position * mark * rate,
    )
    result = simulate_grid(
        GridBacktestInputs(
            params,
            replace(TERMS, maker_fee=_MAKER, taker_fee=_TAKER),
            bars,
            timedelta(minutes=1),
            FineKlinesByCandle({}),
            engine=lambda first: FuturesReplay(params, TERMS, run, first),
        )
    )
    if not isinstance(result, GridBacktestResult):
        raise TypeError("the sample replay was cancelled")
    return result


def futures_result(*, crash: bool = False) -> GridBacktestResult:
    """A Long grid at 5x replayed over minute candles; `crash` drops the price through
    the ladder and through the liquidation price."""
    config = {
        **CONFIG,
        "stop_loss": "off",
        "take_profit": "off",
        "direction": "LONG",
        "leverage": "5",
    }
    closes = ("65000", "64000", "62000", "60500") + (
        ("30000",) if crash else ("61500",)
    )
    opens = ("65000", *closes[:-1])
    bars = tuple(
        _bar(
            index,
            (
                o,
                str(max(Decimal(o), Decimal(c)) + 200),
                str(min(Decimal(o), Decimal(c)) - 200),
                c,
            ),
        )
        for index, (o, c) in enumerate(zip(opens, closes, strict=True))
    )
    return _futures_replay(config, bars, "1 settlement, at the bar's close")
