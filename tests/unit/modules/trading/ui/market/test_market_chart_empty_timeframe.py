"""`BUG-159` — a timeframe with nothing stored must not keep the previous
timeframe's candles under its own label, and must say so in the Output log."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)


def _opened(build, threads):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()
    return presenter, presenter.charts["BTCUSDT"]


def test_a_timeframe_with_no_stored_candles_clears_the_previous_ones(
    build, threads, feed
):
    _presenter, chart = _opened(build, threads)
    assert chart.chart._raw_history, "the 1m window is drawn first"
    feed.empty.add("1s")

    chart.chart.toolbar.sig_timeframe_changed.emit("1s")
    threads.run_all()

    assert chart.chart._raw_history == [], (
        "1s is chosen, so 1m candles must not stay drawn under it"
    )


def test_a_timeframe_with_no_stored_candles_is_said_in_the_log(build, threads, feed):
    presenter, chart = _opened(build, threads)
    feed.empty.add("1s")

    chart.chart.toolbar.sig_timeframe_changed.emit("1s")
    threads.run_all()

    messages = [entry.message for entry in presenter.view.log.entries]
    assert any("BTCUSDT" in m and "1s" in m and "No " in m for m in messages), messages
