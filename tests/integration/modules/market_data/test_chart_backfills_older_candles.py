"""`BUG-177` — a live chart that is panned past its oldest candle loads older
candles, from the store when it has them and from the exchange when it has not,
with a real worker pool, the real candle feed over the market-data ports and a
real `ChartCard`; only the exchange and the store are fakes.

Every chart of the app (a desk's, a Market tab's, a bot's) is a
`LiveCandleChart`, so this is the behaviour of all three.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_chart import BotChart
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    at,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart import (
    DeskChart,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_chart import (
    MarketChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.market_data.contracts.fake_exchange_sync import (
    FakeExchangeSync,
)
from sagittarius_engine.infrastructure.thread_manager import ThreadManager

_SPOT = MarketType.SPOT
_BAR = 60.0
#: The chart's first window: the store's newest 500 candles (`HISTORY_CANDLE_LIMIT`).
_NEWEST = range(1000, 1500)


class _GatedExchange(FakeExchangeSync):
    """An exchange that answers when the test lets it: the backfill is in
    flight while live ticks arrive."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)  # type: ignore[arg-type]
        self.answer = threading.Event()
        self.answer.set()

    def sync(self, request: MarketDataSyncRequest) -> None:
        assert self.answer.wait(timeout=10), "the test never released the exchange"
        super().sync(request)


@pytest.fixture
def threads() -> Iterator[ThreadManager]:
    manager = ThreadManager(max_workers=2, name="test-chart")
    yield manager
    manager.shutdown(wait=True)


def _chart(
    qtbot: QtBot,
    threads: ThreadManager,
    stored: range,
    exchange: range,
) -> tuple[LiveCandleChart, ChartCard, _GatedExchange, RecordingNotifier]:
    store = FakeHistoricalKlines()
    store.seed([candle("BTCUSDT", minute) for minute in [*stored, *_NEWEST]], _SPOT)
    sync = _GatedExchange(
        store, [candle("BTCUSDT", minute) for minute in exchange], _SPOT
    )
    feed = MarketDataCandleFeed(sync, store, FakeMarketStream(), _SPOT)
    notifier = RecordingNotifier()
    card = ChartCard("BTCUSDT")
    qtbot.addWidget(card)
    card.resize(900, 500)
    card.show()
    chart = LiveCandleChart(
        card,
        LiveChartPorts(
            thread_manager=threads,
            feed=feed,
            stream_owner="test.chart",
            interval="1m",
            market=_SPOT,
            notifier=notifier,
            scope="test",
        ),
        parent=card,
    )
    chart.show_symbol("BTCUSDT")
    qtbot.waitUntil(lambda: len(card._raw_history) == len(_NEWEST), timeout=10_000)
    return chart, card, sync, notifier


def _pan_left_past_the_oldest(card: ChartCard) -> None:
    view_box = card.plot_layout.main_plot.vb
    left = card._raw_history[0][0] - 5 * _BAR
    view_box.setXRange(left, left + 30 * _BAR, padding=0)
    view_box.sigRangeChangedManually.emit(view_box.viewRange())


def _times(card: ChartCard) -> list[float]:
    return [row[0] for row in card._raw_history]


def _opens(card: ChartCard) -> list[int]:
    """The minute each drawn candle opens (its x is its close, a bar later)."""
    base = at(0).timestamp()
    return [int((t - base) // _BAR) - 1 for t in _times(card)]


def test_older_candles_come_from_the_store_when_it_has_them(
    qtbot: QtBot, threads: ThreadManager
) -> None:
    chart, card, sync, _notifier = _chart(
        qtbot, threads, stored=range(300, 1000), exchange=range(0)
    )

    _pan_left_past_the_oldest(card)
    qtbot.waitUntil(lambda: len(card._raw_history) == 1000, timeout=10_000)

    assert _opens(card) == list(range(500, 1500))
    assert sync.requests == [], "the store held them: no call to the exchange"
    assert chart.older_candles.loading is False


def test_with_an_empty_store_older_candles_are_fetched_stored_and_drawn(
    qtbot: QtBot, threads: ThreadManager
) -> None:
    _live, card, sync, _notifier = _chart(
        qtbot, threads, stored=range(0), exchange=range(500, 1000)
    )

    _pan_left_past_the_oldest(card)
    qtbot.waitUntil(lambda: len(card._raw_history) == 1000, timeout=10_000)

    assert _opens(card) == list(range(500, 1500))
    assert len(sync.requests) == 1
    request = sync.requests[0]
    assert request.market is _SPOT
    assert (request.start_time, request.end_time) == (at(500), at(1000))


def test_live_ticks_arriving_during_the_backfill_are_kept_and_nothing_overlaps(
    qtbot: QtBot, threads: ThreadManager
) -> None:
    chart, card, sync, _notifier = _chart(
        qtbot, threads, stored=range(0), exchange=range(500, 1000)
    )
    sync.answer.clear()

    _pan_left_past_the_oldest(card)
    qtbot.waitUntil(lambda: chart.older_candles.loading, timeout=10_000)
    for minute in (1500, 1501, 1502):
        chart.apply_candle(candle("BTCUSDT", minute))
        QApplication.processEvents()
    assert len(card._raw_history) == len(_NEWEST) + 3
    sync.answer.set()
    qtbot.waitUntil(lambda: len(card._raw_history) == 1003, timeout=10_000)

    times = _times(card)
    assert times == sorted(set(times)), "oldest first, no candle twice"
    assert _opens(card) == list(range(500, 1503))


def test_an_unreachable_exchange_is_told_and_the_chart_keeps_what_it_has(
    qtbot: QtBot, threads: ThreadManager
) -> None:
    _live, card, sync, notifier = _chart(
        qtbot, threads, stored=range(0), exchange=range(500, 1000)
    )

    def refuse(request: MarketDataSyncRequest) -> None:
        raise ConnectionError("exchange unreachable")

    sync.sync = refuse  # type: ignore[method-assign]

    _pan_left_past_the_oldest(card)
    qtbot.waitUntil(lambda: len(notifier.failures) == 1, timeout=10_000)

    assert len(card._raw_history) == len(_NEWEST)
    assert "exchange unreachable" not in notifier.last.headline
    assert "exchange unreachable" in notifier.last.detail


@pytest.mark.parametrize("chart_class", [DeskChart, MarketChart, BotChart])
def test_every_chart_of_the_app_is_a_live_candle_chart(
    chart_class: type[LiveCandleChart],
) -> None:
    """The desk's, the Market tab's and a bot's chart inherit the backfill: none
    of them keeps a loading path of its own."""
    assert issubclass(chart_class, LiveCandleChart)
