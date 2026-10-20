"""`EPIC-040A` — the Grid's Backtest page, one frame per state worth looking at.

Offline, like `preview.py`. Every frame is the real page driven through its public
surface (`GridBacktest.follow` and a click on its own buttons) over a scripted query
and a held thread pool, so each sentence and each enabled button is the one a user
sees, and the owner can compare a frame before and after `EPIC-040D`/`040F` move the
page. `preview.py` stays the Spot result.

  idle_no_bot · idle_no_market_numbers · idle_ready · running · syncing ·
  refused_candles · refused_funding · spot_result · futures_result ·
  futures_liquidated · cancelled · another_bot

Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview_frames
<frame> [--png path]` (offscreen with `--png`, a window otherwise).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest.result import (
    GridBacktestRefusal,
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
    SampleCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestContext,
    BacktestPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest import (
    GridBacktest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview import (
    CONFIG,
    INTERVAL,
    START,
    SYMBOL,
    TERMS,
    sample_result,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_BRACKETS = LeverageBrackets(
    SYMBOL,
    (
        LeverageBracket(
            1, 125, Decimal(0), Decimal(50_000), Decimal("0.004"), Decimal(0)
        ),
    ),
)
_MAKER = Decimal("0.0002")
_TAKER = Decimal("0.0005")
_NO_CANDLES = GridBacktestRefusal(
    "No 15m candles of BTCUSDT are stored for this period. Sync candles fetches "
    "them, then runs again.",
    missing_candles=True,
)
_NO_FUNDING = GridBacktestRefusal(
    "The funding history of BTCUSDT could not be read for this period.",
    funding_unavailable=True,
)


class _HeldThreads(IThreadManager):
    """Keeps each task until `release` runs it, so a frame can stop mid-run."""

    def __init__(self) -> None:
        self._pending: list[tuple[Callable[..., object], tuple[object, ...]]] = []

    def submit(
        self, task: Callable[..., object], *args: object, **kwargs: object
    ) -> concurrent.futures.Future[object]:
        self._pending.append((task, args))
        return concurrent.futures.Future()

    def run_held(self) -> None:
        while self._pending:
            task, args = self._pending.pop(0)
            task(*args)

    def shutdown(self, wait: bool = True) -> None:
        self._pending.clear()


class _Scripted(ICommandDispatcher):
    """Answers each backtest with the next canned answer."""

    def __init__(self, *answers: object) -> None:
        self._answers = list(answers)

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self._answers.pop(0)


class _Frame:
    """The real page over a scripted query; the frame drives it by its buttons."""

    def __init__(self, *answers: object, futures: bool = False) -> None:
        self.held = _HeldThreads()
        self.backtest = GridBacktest(
            BacktestPorts(
                self.held,
                _Scripted(*answers),
                FakeMarketDataSync(),
                SampleCandleFeed(START, INTERVAL),
                RecordingNotifier(),
            )
        )
        utc = QTimeZone.utc()
        view = self.backtest.view
        view.start.setDateTime(
            QDateTime.fromSecsSinceEpoch(int(START.timestamp()), utc)
        )
        end = START + timedelta(hours=120)
        view.end.setDateTime(QDateTime.fromSecsSinceEpoch(int(end.timestamp()), utc))
        self._futures = futures

    def select_bot(self, bot_id: str = "a3f9c1", *, terms: bool = True) -> _Frame:
        self.backtest.follow(self.context_of(bot_id, terms=terms))
        return self

    def context_of(self, bot_id: str, *, terms: bool = True) -> BacktestContext:
        venue = (
            TradingVenue.FUTURES_TESTNET if self._futures else TradingVenue.SPOT_TESTNET
        )
        brackets = _BRACKETS if self._futures else None
        return BacktestContext(
            bot_id, venue, SYMBOL, CONFIG, TERMS if terms else None, brackets
        )

    def press_run(self) -> _Frame:
        self.backtest.view.run_button.click()
        return self

    def finish_work(self) -> _Frame:
        self.held.run_held()
        return self

    def press(self, button: str) -> _Frame:
        getattr(self.backtest.view, button).click()
        return self

    @property
    def shown(self) -> GridBacktestView:
        view = self.backtest.view
        view.setWindowTitle("Grid backtest — frame")
        return view


def _bar(minute: int, o: str, h: str, low: str, c: str) -> PriceBar:
    return PriceBar(
        START + timedelta(minutes=minute),
        Decimal(o),
        Decimal(h),
        Decimal(low),
        Decimal(c),
    )


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
        _BRACKETS,
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
            o,
            str(max(Decimal(o), Decimal(c)) + 200),
            str(min(Decimal(o), Decimal(c)) - 200),
            c,
        )
        for index, (o, c) in enumerate(zip(opens, closes, strict=True))
    )
    return _futures_replay(config, bars, "1 settlement, at the bar's close")


def _idle_no_bot() -> GridBacktestView:
    return _Frame().shown


def _idle_no_market_numbers() -> GridBacktestView:
    return _Frame().select_bot(terms=False).shown


def _idle_ready() -> GridBacktestView:
    return _Frame().select_bot().shown


def _running() -> GridBacktestView:
    return _Frame(sample_result()).select_bot().press_run().shown


def _syncing() -> GridBacktestView:
    return (
        _Frame(_NO_CANDLES)
        .select_bot()
        .press_run()
        .finish_work()
        .press("sync_button")
        .shown
    )


def _refused_candles() -> GridBacktestView:
    return _Frame(_NO_CANDLES).select_bot().press_run().finish_work().shown


def _refused_funding() -> GridBacktestView:
    frame = _Frame(_NO_FUNDING, futures=True)
    return frame.select_bot().press_run().finish_work().shown


def _spot_result() -> GridBacktestView:
    return _Frame(sample_result()).select_bot().press_run().finish_work().shown


def _futures_result() -> GridBacktestView:
    return (
        _Frame(futures_result(), futures=True)
        .select_bot()
        .press_run()
        .finish_work()
        .shown
    )


def _futures_liquidated() -> GridBacktestView:
    frame = _Frame(futures_result(crash=True), futures=True)
    return frame.select_bot().press_run().finish_work().shown


def _cancelled() -> GridBacktestView:
    frame = (
        _Frame(sample_result(), sample_result()).select_bot().press_run().finish_work()
    )
    return frame.press_run().press("cancel_button").shown


def _another_bot() -> GridBacktestView:
    frame = _Frame(sample_result()).select_bot().press_run().finish_work()
    return frame.select_bot("b7e2d4").shown


FRAMES: Mapping[str, Callable[[], GridBacktestView]] = {
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
}


def build_frame(name: str) -> GridBacktestView:
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
