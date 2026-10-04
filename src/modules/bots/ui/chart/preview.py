"""`EPIC-029G` — a bot's chart with a sample Grid: the report's example (BTC
around 65,000, a 60,000–70,000 range of 10 grids, exits 5% beyond it), a few
fills, the average cost and the ATR zones.

Offline: the candles come from a sample feed (`preview_ports`), and the load
runs on the calling thread, so the preview opens no socket and starts no pool.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PySide6.QtWidgets import QWidget
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.preview_ports import (
    CallingThread,
    SampleCandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)

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
        thread_manager=CallingThread(),
        feed=SampleCandleFeed(_START, _INTERVAL),
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
