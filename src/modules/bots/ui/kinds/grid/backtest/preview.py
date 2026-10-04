"""`EPIC-029D` — the Grid's Backtest page with a sample result: the report's
example (BTC around 65,000, 60,000–70,000, 10 grids, exits 5% beyond it)
replayed on five days of hourly sample candles, coarse (no 1-second klines),
so the summary shows that caveat too.

Offline: the replay runs here through `simulate_grid`, not the query, and the
chart only draws what it is given; nothing opens a socket or starts a pool.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.streamed_fine_klines import (
    price_bar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
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
    CallingThread,
    SampleCandleFeed,
    sample_candle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_summary import (
    chart_candles,
    result_overlay,
    summary_rows,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)

#: The directory is `backtest`, a name the backtesting module's previews could
#: share; the key is explicit (`scripts/preview_qml.py`).
PREVIEW_KEY = "grid_backtest"

_SYMBOL = "BTCUSDT"
_INTERVAL = TimeFrame.ONE_HOUR
_START = datetime(2026, 9, 28, tzinfo=UTC)
_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "10000",
    "stop_loss": "percent:5",
    "take_profit": "percent:5",
}
_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)


def build_preview() -> QWidget:
    view = GridBacktestView(
        LiveChartPorts(
            thread_manager=CallingThread(),
            feed=SampleCandleFeed(_START, _INTERVAL),
            stream_owner="bots.backtest.preview",
            interval=_INTERVAL.value,
        )
    )
    result = _sample_result()
    view.show_replay(
        chart_candles(result, _SYMBOL, _INTERVAL),
        result_overlay(result),
        result.equity,
        summary_rows(result),
    )
    view.setWindowTitle("Grid backtest — sample result")
    return view


def _sample_result() -> GridBacktestResult:
    bars = tuple(
        price_bar(sample_candle(_SYMBOL, _INTERVAL, _START, index))
        for index in range(SAMPLE_CANDLES)
    )
    replay = simulate_grid(
        GridBacktestInputs(
            GridParams.from_config(_CONFIG),
            _TERMS,
            bars,
            timedelta(seconds=_INTERVAL.to_seconds()),
        )
    )
    if not isinstance(replay, GridBacktestResult):
        raise TypeError("the sample replay was cancelled")
    return replay
