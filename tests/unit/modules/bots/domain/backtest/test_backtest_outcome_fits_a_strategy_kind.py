"""`EPIC-040B` — the kind-neutral request and outcome fit a second kind, proven by a stub.

@details The strategy kind (`EPIC-040G`) is not built. This stub adapter implements the port
without importing the Grid and answers the way a strategy would: it reads the warm-up the request
asks for, and its trades are one position at a time, entered and exited, each a labelled fill.
The workbench draws such an outcome with no kind knowledge: the figures, notes and fills are
data, and the strategy's own rich result is the opaque `detail`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    IKindBacktester,
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
    BacktestCancelled,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestBar,
    BacktestFigure,
    BacktestFill,
    BacktestOutcome,
    BacktestProvenance,
    EquityPoint,
    FigureKind,
    FigureTone,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
)

_T0 = datetime(2026, 9, 1, tzinfo=UTC)
_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class _StrategyDetail:
    """What only the strategy kind's own panes read."""

    signals: tuple[str, ...]


class _StubStrategyBacktester(IKindBacktester):
    def __init__(self) -> None:
        self.requests: list[KindBacktestRequest] = []

    def run(self, request: KindBacktestRequest) -> BacktestAnswer:
        self.requests.append(request)
        if request.cancelled():
            return BacktestCancelled(0, 3)
        first = request.start
        bars = tuple(
            BacktestBar(
                first + _HOUR * n,
                Decimal(100 + n),
                Decimal(102 + n),
                Decimal(99 + n),
                Decimal(101 + n),
            )
            for n in range(3)
        )
        return BacktestOutcome(
            provenance=BacktestProvenance(
                tuple(request.config.items()),
                Decimal("0.001"),
                Decimal("0.001"),
                bars[0].time,
                bars[-1].time,
                "a signal acts on the next candle's open",
            ),
            bars=bars,
            equity=tuple(
                EquityPoint(bar.time, Decimal(1000 + 10 * n), Decimal(1000 + n))
                for n, bar in enumerate(bars)
            ),
            fills=(
                BacktestFill(
                    bars[0].time,
                    OrderSide.BUY,
                    Decimal(100),
                    Decimal(1),
                    Decimal("0.1"),
                    "Enter long",
                    False,
                ),
                BacktestFill(
                    bars[2].time,
                    OrderSide.SELL,
                    Decimal(103),
                    Decimal(1),
                    Decimal("0.1"),
                    "Exit",
                    False,
                ),
            ),
            maker_fees=Decimal(0),
            taker_fees=Decimal("0.2"),
            figures=(
                BacktestFigure("trades", "Trades", FigureKind.QUANTITY, 1),
                BacktestFigure(
                    "net",
                    "Net profit (USDT)",
                    FigureKind.MONEY,
                    Decimal("2.8"),
                    FigureTone.GOOD,
                ),
            ),
            notes=("Warm-up candles are replayed but never traded.",),
            detail=_StrategyDetail(("long at 100", "exit at 103")),
        )


def _request(**changes: object) -> KindBacktestRequest:
    fields: dict[str, object] = {
        "symbol": "BTCUSDT",
        "config": {"strategy": "ema_cross", "fast": "9"},
        "terms": TERMS,
        "interval": TimeFrame.ONE_HOUR,
        "start": _T0,
        "end": _T0 + timedelta(days=1),
        "venue": TradingVenue.SPOT_TESTNET,
        **changes,
    }
    return KindBacktestRequest(**fields)  # type: ignore[arg-type]


def test_a_strategy_asks_for_warm_up_history_and_answers_in_trades_not_a_ladder() -> (
    None
):
    backtester = _StubStrategyBacktester()

    answer = backtester.run(_request(warmup=timedelta(hours=200)))

    assert backtester.requests[0].warmup == timedelta(hours=200)
    assert isinstance(answer, BacktestOutcome)
    assert [fill.label for fill in answer.fills] == ["Enter long", "Exit"]
    assert [fill.side for fill in answer.fills] == [OrderSide.BUY, OrderSide.SELL]
    assert answer.figures[1].tone is FigureTone.GOOD
    assert isinstance(answer.detail, _StrategyDetail)


def test_a_cancelled_run_answers_a_value_not_a_partial_outcome() -> None:
    answer = _StubStrategyBacktester().run(_request(cancelled=lambda: True))

    assert answer == BacktestCancelled(0, 3)


def test_the_request_defaults_to_no_warm_up_and_refuses_a_period_that_ends_first() -> (
    None
):
    assert _request().warmup == timedelta(0)
    with pytest.raises(ValueError, match="must end after it starts"):
        _request(end=_T0)
    with pytest.raises(ValueError, match="cannot be negative"):
        _request(warmup=timedelta(hours=-1))


def test_a_kind_with_no_backtest_declares_nothing() -> None:
    class _Bare(IBotKind):
        """The ABC's own abstract members and nothing else."""

        kind_id = "bare"  # type: ignore[assignment]

        def supported_profiles(self):  # type: ignore[no-untyped-def]
            return frozenset()

        def validate(self, inputs):  # type: ignore[no-untyped-def]
            return ()

        def overlay(self, inputs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def executor_factory(self):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    assert _Bare().backtester() is None
