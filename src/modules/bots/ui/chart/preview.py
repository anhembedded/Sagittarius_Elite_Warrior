"""`EPIC-029G` — a bot's chart with a sample Grid: the report's example (BTC
around 65,000, a 60,000–70,000 range of 10 grids, exits 5% beyond it), a few
fills, the average cost and the ATR zones.

Offline: the candles come from a sample feed in this file, and the load runs
on the calling thread, so the preview opens no socket and starts no pool.
"""

from __future__ import annotations

import concurrent.futures
import math
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    FillSide,
    OverlayFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    GridActivity,
    GridOverlaySource,
    LevelState,
    grid_overlay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_chart import BotChart
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_stream_owner import (
    bot_stream_owner,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandleStreamStart,
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

#: This file's parent directory is `chart`, a name another module's preview
#: could share; the key is explicit (`scripts/preview_qml.py`).
PREVIEW_KEY = "bot_chart"

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
    card = ChartCard(_SYMBOL)
    ports = LiveChartPorts(
        thread_manager=_CallingThread(),
        feed=_SampleFeed(),
        stream_owner=bot_stream_owner(BotId("a3f9c1")),
        interval=_INTERVAL.value,
    )
    chart = BotChart(card, ports, parent=card)
    chart.show_symbol(_SYMBOL)
    chart.show_overlay(grid_overlay(_sample_source()))
    card.setWindowTitle("Bot chart — sample Grid")
    return card


def _sample_source() -> GridOverlaySource:
    inputs = BotKindInputs(_CONFIG, _TERMS, MarketView(Decimal(65000), Decimal(2500)))
    evaluation = evaluate_grid(inputs, GridThresholds())
    if evaluation.params is None or evaluation.plan is None:
        raise ValueError(f"the sample Grid is refused: {evaluation.verdicts}")
    fills = (
        OverlayFill(_at(30), Decimal(64000), FillSide.BUY, "L4"),
        OverlayFill(_at(52), Decimal(63000), FillSide.BUY, "L3"),
        OverlayFill(_at(80), Decimal(64000), FillSide.SELL, "L4"),
    )
    activity = GridActivity(
        level_states={3: LevelState.RESTING_SELL, 7: LevelState.PARTIAL},
        fills=fills,
        average_cost=Decimal(63500),
    )
    return GridOverlaySource(
        evaluation.params,
        evaluation.plan,
        GridThresholds(),
        activity=activity,
        daily_atr=Decimal(2500),
    )


def _at(hour: int) -> datetime:
    return _START + timedelta(hours=hour + 1)


class _SampleFeed(ICandleFeed):
    """Five days of hourly candles swinging between the grid's levels."""

    def sync(
        self, symbol: str, interval: TimeFrame, cancelled: Callable[[], bool]
    ) -> None:
        return None

    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        return tuple(_candle(symbol, hour) for hour in range(min(limit, 120)))

    def start_stream(
        self, owner_id: str, symbol: str, interval: TimeFrame
    ) -> CandleStreamStart:
        return CandleStreamStart(False, "The preview does not stream.")

    def stop_stream(self, owner_id: str) -> None:
        return None


def _candle(symbol: str, hour: int) -> MarketData:
    mid = 65000 + 3500 * math.sin(hour / 9) + 600 * math.sin(hour / 2.3)
    open_price = mid - 150 * math.cos(hour)
    close_price = mid + 150 * math.cos(hour)
    return MarketData(
        symbol=symbol,
        interval=_INTERVAL.value,
        open_time=_START + timedelta(hours=hour),
        open_price=open_price,
        high_price=max(open_price, close_price) + 220,
        low_price=min(open_price, close_price) - 220,
        close_price=close_price,
        volume=40 + 15 * abs(math.sin(hour)),
        close_time=_START + timedelta(hours=hour + 1),
        quote_asset_volume=0.0,
        number_of_trades=0,
        taker_buy_base_asset_volume=0.0,
        taker_buy_quote_asset_volume=0.0,
    )


class _CallingThread(IThreadManager):
    """Runs each task at once, on the caller's thread: a preview has nothing
    to wait for and nothing to shut down."""

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None
