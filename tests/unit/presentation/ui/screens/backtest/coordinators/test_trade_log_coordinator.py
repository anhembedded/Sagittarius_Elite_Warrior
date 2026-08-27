"""`TradeLogCoordinator` — exercised with no presenter, no container, no view.

That is the point of `EPIC-003E`'s extraction, and it is what these tests
demonstrate. The equivalent coverage before the split had to build a whole
`BackTestPresenter` behind two `MagicMock`s just to render a table
(`test_backtest_timezone_presenter.py` still does).
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    TradeLogCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.screens.backtest.coordinators.conftest import (
    InMemoryScreenState,
)


class _RecordingLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)


def _trade(pnl: float, entry_hour: int = 4) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=datetime(2026, 8, 17, entry_hour, 0, tzinfo=UTC),
        entry_price=60000.0,
        exit_time=datetime(2026, 8, 17, entry_hour + 4, 0, tzinfo=UTC),
        exit_price=61000.0,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=1.67,
        fees_paid=5.0,
        entry_reason="Signal",
        exit_reason=ExitReason.STRATEGY_SIGNAL,
    )


def _build(trades: list[Trade], export_path: str = "", logger=None):
    """Returns (coordinator, view_model, timezones_pushed_to_the_chart)."""
    view_model = BackTestViewModel()
    pushed: list[str] = []
    coordinator = TradeLogCoordinator(
        view_model=view_model,
        state=InMemoryScreenState(all_trades=trades),
        set_chart_display_timezone=pushed.append,
        ask_export_path=lambda: export_path,
        logger=logger or _RecordingLogger(),
    )
    return coordinator, view_model, pushed


def test_refresh_fills_the_page_state_without_a_presenter(qtbot) -> None:
    coordinator, view_model, _ = _build([_trade(50.0), _trade(-20.0)])

    coordinator.refresh()

    assert len(view_model.tradeLogRows) == 2
    assert view_model.tradeLogTotalCount == 2


def test_the_trade_list_is_read_live_not_captured(qtbot) -> None:
    """The presenter rebinds its trade list on every run, and three existing
    tests assign `presenter._all_trades` directly. A coordinator handed the
    list once would render a stale table in both cases."""
    trades: list[Trade] = []
    view_model = BackTestViewModel()
    coordinator = TradeLogCoordinator(
        view_model=view_model,
        state=InMemoryScreenState(all_trades=trades),
        set_chart_display_timezone=lambda _tz: None,
        ask_export_path=lambda: "",
        logger=_RecordingLogger(),
    )
    coordinator.refresh()
    assert view_model.tradeLogTotalCount == 0

    trades.append(_trade(50.0))
    coordinator.refresh()

    assert view_model.tradeLogTotalCount == 1


def test_export_writes_only_what_the_filter_currently_shows(qtbot, tmp_path) -> None:
    """The export matches what the user is looking at, not everything the run
    produced -- so a filtered table must not export the rows it is hiding."""
    target = tmp_path / "trades.csv"
    coordinator, view_model, _ = _build(
        [_trade(50.0), _trade(-20.0, entry_hour=6)], export_path=str(target)
    )
    view_model.tradeLogFilter = "win"

    coordinator.on_export_requested()

    with target.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) - 1 == 1, f"expected only the winning trade, got {rows}"


def test_export_is_skipped_when_there_is_nothing_to_export(qtbot, tmp_path) -> None:
    target = tmp_path / "trades.csv"
    coordinator, _view_model, _ = _build([], export_path=str(target))

    coordinator.on_export_requested()

    assert not target.exists()


def test_export_is_skipped_when_the_user_cancels_the_dialog(qtbot, tmp_path) -> None:
    """`ask_export_path` returning "" is how a cancelled dialog arrives. The
    check is easy to drop, and dropping it writes a file to path ""."""
    coordinator, _view_model, _ = _build([_trade(50.0)], export_path="")

    coordinator.on_export_requested()

    assert list(tmp_path.iterdir()) == []


def test_a_dirty_config_export_says_which_run_it_came_from(qtbot, tmp_path) -> None:
    """Exporting while the config is dirty gives a CSV of the PREVIOUS run.
    Silently is the wrong way to do that."""
    logger = _RecordingLogger()
    coordinator, view_model, _ = _build(
        [_trade(50.0)], export_path=str(tmp_path / "t.csv"), logger=logger
    )
    view_model.set_ui_mode(BacktestUiState.CONFIG_DIRTY.value)

    coordinator.on_export_requested()

    assert any("Trade Logs" in message for message in logger.messages)


def test_timezone_change_reaches_the_chart_and_re_renders_the_table(qtbot) -> None:
    coordinator, view_model, pushed = _build([_trade(50.0)])
    view_model.setDisplayTimezone("Asia/Ho_Chi_Minh")

    coordinator.on_display_timezone_changed()

    assert pushed == ["Asia/Ho_Chi_Minh"]
    assert view_model.tradeLogTotalCount == 1
