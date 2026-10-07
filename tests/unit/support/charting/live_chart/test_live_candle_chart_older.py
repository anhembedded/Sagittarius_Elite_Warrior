"""`BUG-178`: panning or zooming a live chart left past its oldest candle loads
older candles, on every chart that is a `LiveCandleChart` (desk, Market, a
bot's).

`ChartCard.sig_near_left_edge` lost its only listener when the Dev Board was
deleted (`c7914f0`); the shared chart never listened. Each test drives a real
`LiveCandleChart` over a feed the test scripts, pans the real view box and reads
what the chart drew.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    OlderCandlesRequest,
)
from Sagittarius_Elite_Warrior.tests.unit.support.charting.live_chart.live_chart_fixtures import (
    Clock,
    HeldThreadManager,
    ScriptedCandleFeed,
    build_chart,
)

#: The newest window is minutes 100–159; the older candles are minutes 40–99.
_NEWEST = [candle("BTCUSDT", minute) for minute in range(100, 160)]
_OLDER = [candle("BTCUSDT", minute) for minute in range(40, 100)]
_BAR = 60.0


class OlderFeed(ScriptedCandleFeed):
    """A feed that answers the first window and an older one, and records the
    older reads."""

    def __init__(self) -> None:
        super().__init__()
        self.older: list[MarketData] = list(_OLDER)
        self.older_error: str | None = None
        #: Answers the window with the candles at and after `before` too, as a
        #: store that bounds a read inclusively would.
        self.overlapping = False
        #: The `before` of each older read.
        self.older_reads: list[datetime] = []

    def load_history(
        self, symbol: str, interval: TimeFrame, limit: int
    ) -> Sequence[MarketData]:
        return list(_NEWEST)

    def load_older(
        self, request: OlderCandlesRequest, cancelled: Callable[[], bool]
    ) -> Sequence[MarketData]:
        self.older_reads.append(request.before)
        if self.older_error is not None:
            raise RuntimeError(self.older_error)
        if self.overlapping:
            return [*self.older, *_NEWEST[:3]]
        return [k for k in self.older if k.open_time < request.before]


def _opened(threads: HeldThreadManager | None = None, clock: Clock | None = None):
    feed, notifier = OlderFeed(), RecordingNotifier()
    chart, card = build_chart(feed, clock=clock, threads=threads, notifier=notifier)
    chart.show_symbol("BTCUSDT")
    if threads is not None:
        threads.run_all()
    return feed, chart, card, notifier


def _pan_left_past_the_oldest(card: ChartCard) -> None:
    """What a drag does: the view moves to empty space left of the data, and
    the view box says the user did it."""
    view_box = card.plot_layout.main_plot.vb
    oldest = card._raw_history[0][0]
    left = oldest - 5 * _BAR
    view_box.setXRange(left, left + 30 * _BAR, padding=0)
    view_box.sigRangeChangedManually.emit(view_box.viewRange())


def _times(card: ChartCard) -> list[float]:
    return [row[0] for row in card._raw_history]


def test_panning_past_the_oldest_candle_draws_older_candles(qapp) -> None:
    feed, _chart, card, _notifier = _opened()
    assert len(card._raw_history) == len(_NEWEST)

    _pan_left_past_the_oldest(card)

    assert len(card._raw_history) == len(_OLDER) + len(_NEWEST)
    times = _times(card)
    assert times == sorted(set(times)), "oldest first, no candle twice"
    assert feed.older_reads == [_NEWEST[0].open_time]


def test_older_candles_are_drawn_in_the_volume_plot_too(qapp) -> None:
    _feed, _chart, card, _notifier = _opened()

    _pan_left_past_the_oldest(card)

    assert len(card.volume.as_tuples()) == len(_OLDER) + len(_NEWEST)


def test_a_live_tick_during_the_backfill_is_kept_and_nothing_overlaps(qapp) -> None:
    threads = HeldThreadManager()
    _feed, chart, card, _notifier = _opened(threads)
    _pan_left_past_the_oldest(card)
    assert len(threads.held) == 1, "the older read is in flight"

    live = candle("BTCUSDT", 160)
    chart.apply_candle(live)
    threads.run_all()

    times = _times(card)
    assert len(times) == len(_OLDER) + len(_NEWEST) + 1
    assert times == sorted(set(times)), "oldest first, no candle twice"
    assert times[-1] == live.close_time.timestamp()


def test_a_second_pan_while_one_load_runs_asks_once(qapp) -> None:
    threads = HeldThreadManager()
    feed, _chart, card, _notifier = _opened(threads)

    _pan_left_past_the_oldest(card)
    _pan_left_past_the_oldest(card)
    threads.run_all()

    assert len(feed.older_reads) == 1


def test_a_chart_with_no_older_candles_stops_asking_for_a_while(qapp) -> None:
    clock = Clock()
    feed, _chart, card, _notifier = _opened(clock=clock)
    feed.older = []

    _pan_left_past_the_oldest(card)
    _pan_left_past_the_oldest(card)
    assert len(feed.older_reads) == 1, (
        "the start of the data is not asked again at once"
    )

    clock.now += 60.0
    _pan_left_past_the_oldest(card)
    assert len(feed.older_reads) == 2, (
        "and is asked again later: the store may have grown"
    )
    assert len(card._raw_history) == len(_NEWEST)


def test_a_failed_backfill_is_told_and_leaves_the_chart_as_it_was(qapp) -> None:
    feed, _chart, card, notifier = _opened()
    feed.older_error = "exchange unreachable"

    _pan_left_past_the_oldest(card)

    assert len(card._raw_history) == len(_NEWEST)
    assert len(notifier.failures) == 1
    assert "exchange unreachable" not in notifier.last.headline
    assert "exchange unreachable" in notifier.last.detail


def test_a_load_in_flight_when_the_symbol_changes_draws_nothing(qapp) -> None:
    threads = HeldThreadManager()
    _feed, chart, card, _notifier = _opened(threads)
    _pan_left_past_the_oldest(card)

    chart.show_symbol("ETHUSDT")
    threads.run_all()

    assert len(card._raw_history) == len(_NEWEST)


def test_a_candle_the_window_holds_again_is_not_drawn_twice(qapp) -> None:
    feed, _chart, card, _notifier = _opened()
    feed.overlapping = True

    _pan_left_past_the_oldest(card)

    times = _times(card)
    assert len(times) == len(_OLDER) + len(_NEWEST)
    assert times == sorted(set(times))


def test_a_range_drawn_while_a_load_runs_drops_that_load(qapp) -> None:
    """A range replaces the whole drawn history; an older window asked
    against what it replaced would join the wrong candles."""
    threads = HeldThreadManager()
    _feed, chart, card, _notifier = _opened(threads)
    _pan_left_past_the_oldest(card)

    chart.draw_history(_NEWEST[10:20])
    threads.run_all()

    assert len(card._raw_history) == 10
    assert not chart.older_candles.loading


def test_an_answer_of_a_replaced_request_is_not_taken_for_the_one_now_asked(
    qapp,
) -> None:
    """The first load's answer arrives after the chart moved on and asked
    again: it carries its own token, so it is not drawn as the second's."""
    threads = HeldThreadManager()
    _feed, chart, card, _notifier = _opened(threads)
    _pan_left_past_the_oldest(card)
    old_token = chart._token
    chart.show_symbol("ETHUSDT")
    threads.held.pop(0)  # the first load never runs
    threads.run_all()  # the new first window draws
    _pan_left_past_the_oldest(card)
    assert chart.older_candles.loading

    chart.older_candles.deliver_ready(old_token, list(_OLDER))

    assert len(card._raw_history) == len(_NEWEST)
    assert chart.older_candles.loading
