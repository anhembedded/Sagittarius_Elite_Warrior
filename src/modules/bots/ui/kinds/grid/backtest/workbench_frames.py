"""`EPIC-040D` — the Backtest workbench with the Grid as its one kind, one frame per state worth looking at.

Offline, like `preview_frames.py` (`EPIC-040A`, the Grid's own page, which it replaces in `EPIC-040F`).
Every frame is the real workbench driven through its public surface (`follow` and a click on its own
buttons) over a held thread pool, so each sentence and each enabled button is the one a user sees; the
frames are the same states under the same names, so the owner can lay a 040A frame beside its workbench
frame. The answers are scripted, except the refusal for candles that are not stored, which the real
query handler produces over an empty store.

  idle_no_bot · idle_no_market_numbers · idle_ready · running · syncing · refused_candles ·
  refused_funding · spot_result · futures_result · futures_liquidated · cancelled · another_bot ·
  another_bot_mid_run · edited · edits_question

Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.workbench_frames
<frame> [--png path]` (offscreen with `--png`, a window otherwise).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    GridKindBacktester,
    outcome_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
    RunBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    MarketView,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
    GridKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    BacktestWorkbench,
    WorkbenchPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.preview_ports import (
    HeldPool,
    SampleCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview import (
    CONFIG,
    INTERVAL,
    START,
    SYMBOL,
    TERMS,
    sample_result,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview_frames import (
    BRACKETS,
    funding_refusal,
    futures_result,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import panel_for
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)

type _Answer = object | Callable[[RunBacktestQuery], object]

_CREATED = datetime(2026, 9, 1, tzinfo=UTC)
_PRICE = Decimal(65000)


class _Scripted:
    """Answers each backtest with the next canned answer; a callable is given the query."""

    def __init__(self, *answers: _Answer) -> None:
        self._answers = list(answers)

    def __call__(self, query: RunBacktestQuery) -> BacktestAnswer:
        answer = self._answers.pop(0)
        return cast(BacktestAnswer, answer(query) if callable(answer) else answer)


def candles_refusal(query: RunBacktestQuery) -> object:
    """What the real neutral handler answers for a period with no stored candles: it runs the Grid's
    own backtester over empty verified fakes, so the sentence is the application's own."""
    sources = FakeMarketDataSources().serving(
        FakeMarketDataSources.ports(query.request.venue.market_data_venue)
    )
    grid = GridKind(
        None,  # type: ignore[arg-type]
        GridThresholds(),
        GridKindBacktester(RunGridBacktestQueryHandler(sources)),
    )
    return RunBacktestQueryHandler(BotKindCatalog([grid])).execute(query)


def futures_funding_refusal() -> BacktestRefusal:
    refusal = funding_refusal()
    return BacktestRefusal(
        refusal.reason, funding_unavailable=refusal.funding_unavailable
    )


def _bot(bot_id: str, venue: TradingVenue) -> BotSnapshot:
    return BotSnapshot(
        bot_id=bot_id,
        name=f"bot {bot_id}",
        kind=GRID_KIND_ID,
        venue=venue,
        symbol=SYMBOL,
        state=BotLifecycleState.STOPPED,
        created_at=_CREATED,
        run_started_at=None,
        config=CONFIG,
    )


class _Frame:
    """The real workbench over scripted answers; the frame drives it by its buttons."""

    def __init__(self, *answers: _Answer, futures: bool = False) -> None:
        self.held = HeldPool()
        catalog = BotKindCatalog([GridKind(None, GridThresholds())])  # type: ignore[arg-type]
        self.workbench = BacktestWorkbench(
            WorkbenchPorts(
                self.held,
                _Scripted(*answers),
                FakeMarketDataSync(),
                SampleCandleFeed(START, INTERVAL),
                RecordingNotifier(),
                display_timezone=DisplayTimezonePreference(),
                kinds=catalog.kind,
                editors=panel_for,
            )
        )
        utc = QTimeZone.utc()
        view = self.workbench.view
        view.start.setDateTime(
            QDateTime.fromSecsSinceEpoch(int(START.timestamp()), utc)
        )
        end = START + timedelta(hours=120)
        view.end.setDateTime(QDateTime.fromSecsSinceEpoch(int(end.timestamp()), utc))
        view.interval.set_active(INTERVAL.value)
        self._futures = futures

    def select_bot(self, bot_id: str = "a3f9c1", *, terms: bool = True) -> _Frame:
        venue = (
            TradingVenue.FUTURES_TESTNET if self._futures else TradingVenue.SPOT_TESTNET
        )
        market = PlannerMarket(
            terms=TERMS if terms else None,
            market=MarketView(_PRICE, foreign_open_orders=3),
            atr_range=None,
            bollinger=None,
        )
        risk = (
            PlanRiskFacts(
                FuturesSymbolSetting(SYMBOL, 5, MarginType.ISOLATED, Decimal(10**9)),
                BRACKETS,
            )
            if self._futures
            else None
        )
        self.workbench.follow(WorkbenchSelection(_bot(bot_id, venue), market, risk))
        return self

    def press_run(self) -> _Frame:
        self.workbench.view.run_button.click()
        return self

    def finish_work(self) -> _Frame:
        self.held.run_all()
        return self

    def press(self, button: str) -> _Frame:
        getattr(self.workbench.view, button).click()
        return self

    def edit(self, **changes: str) -> _Frame:
        self.workbench.view.config_edited.emit({**CONFIG, **changes})
        return self

    @property
    def shown(self) -> BacktestWorkbenchView:
        view = self.workbench.view
        view.setWindowTitle("Backtest workbench — frame")
        return view


def _spot() -> object:
    return outcome_of(sample_result())


def _idle_no_bot() -> BacktestWorkbenchView:
    return _Frame().shown


def _idle_no_market_numbers() -> BacktestWorkbenchView:
    return _Frame().select_bot(terms=False).shown


def _idle_ready() -> BacktestWorkbenchView:
    return _Frame().select_bot().shown


def _running() -> BacktestWorkbenchView:
    return _Frame(_spot()).select_bot().press_run().shown


def _syncing() -> BacktestWorkbenchView:
    return (
        _Frame(candles_refusal)
        .select_bot()
        .press_run()
        .finish_work()
        .press("sync_button")
        .shown
    )


def _refused_candles() -> BacktestWorkbenchView:
    return _Frame(candles_refusal).select_bot().press_run().finish_work().shown


def _refused_funding() -> BacktestWorkbenchView:
    frame = _Frame(futures_funding_refusal(), futures=True)
    return frame.select_bot().press_run().finish_work().shown


def _spot_result() -> BacktestWorkbenchView:
    return _Frame(_spot()).select_bot().press_run().finish_work().shown


def _futures_result() -> BacktestWorkbenchView:
    answer = outcome_of(futures_result())
    return _Frame(answer, futures=True).select_bot().press_run().finish_work().shown


def _futures_liquidated() -> BacktestWorkbenchView:
    answer = outcome_of(futures_result(crash=True))
    return _Frame(answer, futures=True).select_bot().press_run().finish_work().shown


def _cancelled() -> BacktestWorkbenchView:
    frame = _Frame(_spot(), _spot()).select_bot().press_run().finish_work()
    return frame.press_run().press("cancel_button").shown


def _another_bot() -> BacktestWorkbenchView:
    frame = _Frame(_spot()).select_bot().press_run().finish_work()
    return frame.select_bot("b7e2d4").shown


def _another_bot_mid_run() -> BacktestWorkbenchView:
    frame = _Frame(_spot()).select_bot().press_run()
    return frame.select_bot("b7e2d4").finish_work().shown


def _edited() -> BacktestWorkbenchView:
    frame = _Frame(_spot()).select_bot().edit(upper="71000")
    return frame.press_run().finish_work().shown


def _edits_question() -> BacktestWorkbenchView:
    frame = _Frame().select_bot().edit(upper="71000")
    return frame.select_bot("b7e2d4").shown


FRAMES: Mapping[str, Callable[[], BacktestWorkbenchView]] = {
    "idle_no_bot": _idle_no_bot,
    "idle_no_market_numbers": _idle_no_market_numbers,
    "idle_ready": _idle_ready,
    "running": _running,
    "syncing": _syncing,
    "refused_candles": _refused_candles,
    "refused_funding": _refused_funding,
    "spot_result": _spot_result,
    "futures_result": _futures_result,
    "futures_liquidated": _futures_liquidated,
    "cancelled": _cancelled,
    "another_bot": _another_bot,
    "another_bot_mid_run": _another_bot_mid_run,
    "edited": _edited,
    "edits_question": _edits_question,
}


def build_frame(name: str) -> BacktestWorkbenchView:
    """@raise KeyError `name` is not one of `FRAMES`."""
    return FRAMES[name]()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frame", choices=sorted(FRAMES))
    parser.add_argument(
        "--png", metavar="PATH", help="Save the frame instead of showing it."
    )
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    widget = build_frame(args.frame)
    widget.resize(1280, 800)
    if args.png:
        widget.grab().save(args.png)
        widget.shutdown()
        return
    widget.show()
    app.exec()


if __name__ == "__main__":
    main()
