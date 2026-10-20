"""`EPIC-040D` — the Backtest workbench with no kind in sight: the page in its idle state, then a
sample replay (candles, an equity curve, two figures) shown the way any kind's result is.

Offline: the candles come from a sample feed and the load runs on the calling thread, so the preview
opens no socket and starts no pool. The workbench with the Grid registered, one frame per state, is
`ui/kinds/grid/backtest/workbench_frames.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    BOT_MARKET,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    EquityPoint,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
    OutcomeShown,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_state import (
    WorkbenchState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_words import (
    DONE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.preview_ports import (
    CallingThread,
    SampleCandleFeed,
    sample_candle,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind, ColumnSpec

#: This file's parent directory is `backtest_workbench`; the key is explicit so no other package's
#: preview can shadow it (`scripts/preview_qml.py`).
PREVIEW_KEY = "backtest_workbench"

_SYMBOL = "BTCUSDT"
_INTERVAL = TimeFrame.FIFTEEN_MINUTES
_START = datetime(2026, 9, 28, tzinfo=UTC)
_BARS = 96


def build_preview() -> QWidget:
    view = BacktestWorkbenchView(
        LiveChartPorts(
            thread_manager=CallingThread(),
            feed=SampleCandleFeed(_START, _INTERVAL),
            stream_owner="bots.backtest",
            interval=_INTERVAL.value,
            market=BOT_MARKET,
            notifier=RecordingNotifier(),
            scope=BOTS_ROUTE,
            live_commands=False,
        )
    )
    candles = [
        sample_candle(_SYMBOL, _INTERVAL, _START, index) for index in range(_BARS)
    ]
    step = timedelta(seconds=_INTERVAL.to_seconds())
    equity = [
        EquityPoint(
            _START + step * (index + 1),
            Decimal(10_000 + 6 * index),
            Decimal(10_000 + (candle.close_price - candles[0].open_price) / 20),
        )
        for index, candle in enumerate(candles)
    ]
    readout = Readout(
        (
            ColumnSpec("candles", "Candles", ColumnKind.QUANTITY),
            ColumnSpec("return", "Return", ColumnKind.PERCENT),
        ),
        {"candles": Decimal(_BARS), "return": Decimal("0.057")},
    )
    view.show_state(WorkbenchState(status=DONE))
    view.show_outcome(
        OutcomeShown(
            candles, BotOverlay(), equity, readout, ("A sample, not a replay.",), ()
        )
    )
    view.setWindowTitle("Backtest workbench — sample result")
    return view
