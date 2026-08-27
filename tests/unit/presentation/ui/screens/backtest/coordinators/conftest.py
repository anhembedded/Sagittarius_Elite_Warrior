"""A single in-memory `IBacktestScreenState` for every coordinator test.

@details `EPIC-012C`. One shared implementation rather than a hand-rolled
fake per test module, because `architecture-rule.md` §2 warns about exactly
that: a double left behind an interface change instantiates fine until the
moment something runs it. With an ABC there is no "until" — a missing member
raises `TypeError: Can't instantiate abstract class` on the first test that
builds one, and there is only one place to fix.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.ports import (
    IBacktestScreenState,
)


class InMemoryScreenState(IBacktestScreenState):
    """Plain attributes, no presenter — what a coordinator test needs.

    @details Deliberately mutable: several tests assign to it *after*
    building the coordinator, which is the reading-late behaviour the real
    `PresenterBackedScreenState` has to preserve. A test that could not do
    that would not catch the early-binding class of defect `EPIC-003E` hit
    four times.

    The class-level assignments below are what actually satisfies the ABC.
    Bare annotations do not: `abc` looks for a *binding* in the class
    namespace, and `symbol: str` creates none, so an annotated-only version
    still raises `TypeError: Can't instantiate abstract class`. That is the
    ABC being loud in the way §2.1 wants — it just has to be answered with
    a value, not a type.
    """

    # Placeholders only — `__init__` overwrites every one of them on each
    # instance. `None` rather than `[]` for the collections: a mutable class
    # attribute would be shared by every state object in the suite, and one
    # test's appended kline would show up in the next (`ruff` RUF012 flags
    # exactly this). Real types live on `IBacktestScreenState`.
    symbol = "BTCUSDT"
    all_trades: Any = None
    active_strategy_lines: Any = None
    chart_klines_fetch_limit = 1000
    active_preview_id = 0
    strategy_params: Any = None
    current_raw_klines: Any = None
    chart_script_keys: Any = None

    def __init__(
        self,
        *,
        symbol: str = "BTCUSDT",
        all_trades: list[Any] | None = None,
        active_strategy_lines: Any = None,
        chart_klines_fetch_limit: int = 1000,
        active_preview_id: int = 0,
        strategy_params: dict[str, Any] | None = None,
        current_raw_klines: list[Any] | None = None,
        chart_script_keys: list[str] | None = None,
    ) -> None:
        # Every collection is rebuilt per instance; the class attributes above
        # exist only so `abc` sees a binding for each abstract member.
        self.symbol = symbol
        self.all_trades = all_trades if all_trades is not None else []
        self.active_strategy_lines = (
            active_strategy_lines if active_strategy_lines is not None else {}
        )
        self.chart_klines_fetch_limit = chart_klines_fetch_limit
        self.active_preview_id = active_preview_id
        self.strategy_params = strategy_params
        self.current_raw_klines = (
            current_raw_klines if current_raw_klines is not None else []
        )
        self.chart_script_keys = (
            chart_script_keys if chart_script_keys is not None else []
        )


@pytest.fixture
def screen_state() -> InMemoryScreenState:
    """A fresh, empty screen state per test."""
    return InMemoryScreenState()


# ---------------------------------------------------------------------- #
# Chart-side doubles, shared by the render and preview coordinator tests.
#
# `EPIC-012D` split `ChartRenderCoordinator` in two; both halves talk to the
# same fake View, toolbar, card and ViewModel. One copy here rather than one
# per test module, for the reason the state double above is shared: a double
# duplicated per module falls behind a contract change silently
# (`architecture-rule.md` §2).
# ---------------------------------------------------------------------- #


class FakeChartCard:
    def __init__(self) -> None:
        self.overlays: list[tuple[str, str, int]] = []
        self.data: list[tuple[str, int]] = []
        self.regions: list[tuple[str, int]] = []

    def add_overlay_indicator(self, name, color, width):
        self.overlays.append((name, color, width))

    def update_indicator_data(self, name, x, y):
        self.data.append((name, len(x)))

    def set_script_regions(self, key, spans):
        self.regions.append((key, len(spans)))


class FakeChartControls:
    def __init__(self, ema_checked=True) -> None:
        self.flags_enabled: list[bool] = []
        self.ema_enabled: list[bool] = []
        self._ema_checked = ema_checked

    def set_trade_flags_enabled(self, v):
        self.flags_enabled.append(v)

    def set_ema_enabled(self, v):
        self.ema_enabled.append(v)

    def is_ema_checked(self):
        return self._ema_checked


class FakeBacktestView:
    def __init__(self, card=None, ema_checked=True) -> None:
        self.chart_cards = [card] if card else []
        self.chart_controls = FakeChartControls(ema_checked)
        self.modes: list = []
        self.backtest_data: list = []
        self.preview_data: list = []

    def set_chart_mode(self, mode):
        self.modes.append(mode)

    def on_backtest_data_ready(self, result, klines, volume):
        self.backtest_data.append((len(klines), len(volume)))

    def on_preview_data_ready(self, klines, volume):
        self.preview_data.append((len(klines), len(volume)))


class FakeChartViewModel:
    def __init__(self) -> None:
        self.preview_mode: list[bool] = []
        self.coverage: list[tuple[bool, str]] = []
        self.needs_sync: list[bool] = []
        self.timeRangePreset = "1M"

    def set_chart_preview_mode(self, v):
        self.preview_mode.append(v)

    def set_data_coverage(self, ok, message):
        self.coverage.append((ok, message))

    def set_needs_data_sync(self, v):
        self.needs_sync.append(v)


# ---------------------------------------------------------------------- #
# Run-side doubles, shared by the execution and chart-feed coordinator tests.
#
# `EPIC-012E` split `ExecutionCoordinator` in two; both halves need the same
# fake dispatcher, run config and result. Shared here for the same reason as
# everything else in this file (`architecture-rule.md` §2).
# ---------------------------------------------------------------------- #


class FakeCancellationToken:
    def __init__(self, cancelled=False) -> None:
        self._cancelled = cancelled

    def is_cancelled(self) -> bool:
        return self._cancelled


def run_config(mode=BacktestExecutionMode.BAR_CLOSE):
    """The real `BacktestRunConfig`, not a stand-in: both run commands are
    pydantic models that validate `position_sizing` and `broker_config`
    against their real types, so a `SimpleNamespace` turned every test into a
    validation error instead of exercising its branch."""
    return BacktestRunConfig(
        strategy_key="s1",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=1000.0,
        start_time=None,
        end_time=None,
        execution_mode=mode,
    )


def committed_bar():
    """Enough of a `MarketData` for `map_klines`/`map_volume` to read."""
    return SimpleNamespace(
        close_time=datetime(2026, 8, 17, tzinfo=UTC),
        open_price=1.0,
        high_price=2.0,
        low_price=0.5,
        close_price=1.5,
        volume=10.0,
    )


def backtest_result(trades=(), committed=()):
    return SimpleNamespace(
        trades=list(trades),
        committed_bars=list(committed),
        metrics=SimpleNamespace(net_profit_percent=1.0),
    )


class RecordingDispatcher:
    def __init__(self, result=None, raises=None, coverage=None) -> None:
        self.result = result
        self.raises = raises
        self.coverage = coverage
        self.commands: list = []

    def dispatch(self, kind, payload):
        self.commands.append(payload)
        if self.raises:
            raise self.raises
        if "Klines" in kind.__name__:
            return SimpleNamespace(data=[])
        return self.result
