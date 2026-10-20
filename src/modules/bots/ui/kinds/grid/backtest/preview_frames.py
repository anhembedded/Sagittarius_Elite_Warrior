"""`EPIC-040A` — the Grid's Backtest page, one frame per state worth looking at.

Offline, like `preview.py`. Every frame is the real page driven through its public
surface (`GridBacktest.follow` and a click on its own buttons) over a scripted query
and a held thread pool, so each sentence and each enabled button is the one a user
sees, and the owner can compare a frame before and after `EPIC-040D`/`040F` move the
page. `preview.py` stays the Spot result.

  idle_no_bot · idle_no_market_numbers · idle_ready · running · syncing ·
  refused_candles · refused_funding · spot_result · futures_result ·
  futures_liquidated · cancelled · another_bot · another_bot_mid_run

Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview_frames
<frame> [--png path]` (offscreen with `--png`, a window otherwise).
"""

from __future__ import annotations

import argparse
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestRefusal,
    RunGridBacktestQuery,
    RunGridBacktestQueryHandler,
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
    HeldPool,
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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
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


def candles_refusal(query: RunGridBacktestQuery) -> GridBacktestRefusal:
    """What the real query handler answers for a period with no stored candles: it runs
    over empty verified fakes, so the sentence is the application's own."""
    handler = RunGridBacktestQueryHandler(
        FakeMarketDataSources().serving(
            FakeMarketDataSources.ports(query.venue.market_data_venue)
        )
    )
    answer = handler.execute(query)
    if not isinstance(answer, GridBacktestRefusal):
        raise TypeError("an empty store must refuse the period")
    return answer


def funding_refusal(reason: str = _FUNDING_DOWN) -> GridBacktestRefusal:
    """What the query answers when a Futures period's funding cannot be read
    (`futures_preparation._without_history`); a unit test holds it equal to the real one. It is
    canned because the real answer needs a Futures store and a failing funding history."""
    return GridBacktestRefusal(
        f"{reason} A Futures backtest without funding flatters a leveraged "
        "grid, so none was run.",
        funding_unavailable=True,
    )


type _Answer = object | Callable[[RunGridBacktestQuery], object]


class _Scripted(ICommandDispatcher):
    """Answers each backtest with the next canned answer; a callable is given the query."""

    def __init__(self, *answers: _Answer) -> None:
        self._answers = list(answers)

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        answer = self._answers.pop(0)
        if callable(answer) and isinstance(input_dto, RunGridBacktestQuery):
            return answer(input_dto)
        return answer


class _Frame:
    """The real page over a scripted query; the frame drives it by its buttons."""

    def __init__(self, *answers: _Answer, futures: bool = False) -> None:
        self.held = HeldPool()
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
        view.interval.setCurrentIndex(view.interval.findData(INTERVAL.value))
        self._futures = futures

    def select_bot(self, bot_id: str = "a3f9c1", *, terms: bool = True) -> _Frame:
        self.backtest.follow(self.context_of(bot_id, terms=terms))
        return self

    def context_of(self, bot_id: str, *, terms: bool = True) -> BacktestContext:
        venue = (
            TradingVenue.FUTURES_TESTNET if self._futures else TradingVenue.SPOT_TESTNET
        )
        brackets = BRACKETS if self._futures else None
        return BacktestContext(
            bot_id, venue, SYMBOL, CONFIG, TERMS if terms else None, brackets
        )

    def press_run(self) -> _Frame:
        self.backtest.view.run_button.click()
        return self

    def finish_work(self) -> _Frame:
        self.held.run_all()
        return self

    def press(self, button: str) -> _Frame:
        getattr(self.backtest.view, button).click()
        return self

    @property
    def shown(self) -> GridBacktestView:
        view = self.backtest.view
        view.setWindowTitle("Grid backtest — frame")
        return view


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
        _Frame(candles_refusal)
        .select_bot()
        .press_run()
        .finish_work()
        .press("sync_button")
        .shown
    )


def _refused_candles() -> GridBacktestView:
    return _Frame(candles_refusal).select_bot().press_run().finish_work().shown


def _refused_funding() -> GridBacktestView:
    frame = _Frame(funding_refusal(), futures=True)
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


def _another_bot_mid_run() -> GridBacktestView:
    frame = _Frame(sample_result()).select_bot().press_run()
    return frame.select_bot("b7e2d4").finish_work().shown


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
    "another_bot_mid_run": _another_bot_mid_run,
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
