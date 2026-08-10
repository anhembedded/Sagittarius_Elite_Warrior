"""Tests for HistoryPaginationController (BOT-035)."""

import time

from Binace_Bot.src.presentation.ui.screens.dashboard.history_pagination_controller import (
    HistoryPaginationController,
)


def test_on_near_left_edge_calls_fetch_older_with_the_given_args(qapp):
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t))
    )

    controller.on_near_left_edge("ETHUSDT", 1000.0)

    assert calls == [("ETHUSDT", 1000.0)]


def test_a_second_near_left_edge_while_in_flight_is_a_no_op(qapp):
    """The user keeps panning near the edge while the first fetch is still
    running — must not submit a second overlapping fetch for the same symbol."""
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t))
    )

    controller.on_near_left_edge("ETHUSDT", 1000.0)
    controller.on_near_left_edge("ETHUSDT", 999.0)
    controller.on_near_left_edge("ETHUSDT", 998.0)

    assert calls == [("ETHUSDT", 1000.0)]


def test_a_different_symbol_is_not_blocked_by_another_symbols_in_flight_fetch(qapp):
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t))
    )

    controller.on_near_left_edge("ETHUSDT", 1000.0)
    controller.on_near_left_edge("BTCUSDT", 2000.0)

    assert calls == [("ETHUSDT", 1000.0), ("BTCUSDT", 2000.0)]


def test_on_load_more_finished_unlocks_the_symbol_for_another_fetch(qapp):
    """cooldown_seconds=0 isolates the in-flight/unlock behavior itself from
    the cooldown gate added afterward (see the cooldown-specific tests below)
    — this test predates the cooldown and would otherwise be racing real
    wall-clock time for no reason."""
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t)), cooldown_seconds=0
    )
    controller.on_near_left_edge("ETHUSDT", 1000.0)

    controller.on_load_more_finished("ETHUSDT", found_more=True)
    controller.on_near_left_edge("ETHUSDT", 900.0)

    assert calls == [("ETHUSDT", 1000.0), ("ETHUSDT", 900.0)]


def test_on_load_more_finished_for_a_symbol_never_in_flight_is_a_safe_no_op(qapp):
    controller = HistoryPaginationController(fetch_older=lambda s, t: None)

    controller.on_load_more_finished("ETHUSDT", found_more=True)  # must not raise


# ---------------------------------------------------------------------------
# Cooldown — the in-flight guard alone only stops OVERLAPPING fetches; a
# real, sustained scroll/drag near the edge delivers many discrete
# sigRangeChangedManually events, and without a cooldown the instant one
# fetch finishes the next already-queued event starts another immediately.
# Real bug, reported from the running app: "Loaded N older klines" logged
# roughly once a second for as long as the user kept scrolling near the edge.
#
# Real tiny sleeps rather than a fake/injected clock, matching this
# codebase's existing convention for time-based tests (see
# test_autostart_controller.py's fallback_seconds=0.05 + qtbot.wait()).
# ---------------------------------------------------------------------------

_TINY_COOLDOWN = 0.05


def test_a_near_left_edge_shortly_after_the_last_fetch_finished_is_a_no_op(qapp):
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t)), cooldown_seconds=_TINY_COOLDOWN
    )
    controller.on_near_left_edge("ETHUSDT", 1000.0)
    controller.on_load_more_finished("ETHUSDT", found_more=True)

    controller.on_near_left_edge("ETHUSDT", 900.0)  # well within the cooldown window

    assert calls == [("ETHUSDT", 1000.0)]


def test_a_near_left_edge_after_the_cooldown_window_elapses_triggers_again(qapp):
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t)), cooldown_seconds=_TINY_COOLDOWN
    )
    controller.on_near_left_edge("ETHUSDT", 1000.0)
    controller.on_load_more_finished("ETHUSDT", found_more=True)

    time.sleep(_TINY_COOLDOWN * 2)
    controller.on_near_left_edge("ETHUSDT", 900.0)

    assert calls == [("ETHUSDT", 1000.0), ("ETHUSDT", 900.0)]


def test_cooldown_is_tracked_per_symbol(qapp):
    """A symbol still cooling down must not block a different symbol that
    has never fetched before."""
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t)), cooldown_seconds=_TINY_COOLDOWN
    )
    controller.on_near_left_edge("ETHUSDT", 1000.0)
    controller.on_load_more_finished("ETHUSDT", found_more=True)

    controller.on_near_left_edge("ETHUSDT", 900.0)  # blocked — still cooling down
    controller.on_near_left_edge("BTCUSDT", 2000.0)  # unaffected — different symbol

    assert calls == [("ETHUSDT", 1000.0), ("BTCUSDT", 2000.0)]


def test_a_fetch_that_found_more_data_reschedules_a_recheck_after_cooldown(qapp, qtbot):
    """If the user zooms out massively with a single scroll wheel tick, we
    get exactly one sigRangeChangedManually event. It triggers a fetch, but
    one batch may not be enough to fill the gap. As long as each fetch keeps
    finding older candles (found_more=True), HistoryPaginationController
    reschedules a recheck after cooldown — which in reality will cause
    another near_left_edge event, closing the gap over a few cooldown
    windows instead of getting stuck after the first one.
    """
    calls = []
    rechecks = []

    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t)),
        cooldown_seconds=_TINY_COOLDOWN,
        recheck_edge=lambda s: rechecks.append(s),
    )

    # 1. User zooms out massively -> one event is fired.
    controller.on_near_left_edge("ETHUSDT", 1000.0)
    assert len(calls) == 1

    # 2. Fetch finishes, having found more (older) candles. Cooldown starts.
    controller.on_load_more_finished("ETHUSDT", found_more=True)

    # 3. Wait for cooldown to expire
    qtbot.wait(int(_TINY_COOLDOWN * 1000) + 50)

    # 4. _recheck_edge should have been called automatically by the QTimer
    assert rechecks == ["ETHUSDT"]


def test_a_fetch_that_found_nothing_does_not_reschedule_a_recheck(qapp, qtbot):
    """The critical counterpart to the test above: once a fetch comes back
    with found_more=False (the symbol's history is exhausted — Phase 1 has
    no auto-sync-from-Binance to ever change that), nothing about the view
    can have moved, so an auto-recheck would just refire the same fetch,
    get nothing again, and reschedule itself forever — an unbounded loop
    hammering the DB with zero further user interaction. Regression guard
    for exactly that bug."""
    rechecks = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: None,
        cooldown_seconds=_TINY_COOLDOWN,
        recheck_edge=lambda s: rechecks.append(s),
    )

    controller.on_near_left_edge("ETHUSDT", 1000.0)
    controller.on_load_more_finished("ETHUSDT", found_more=False)

    qtbot.wait(int(_TINY_COOLDOWN * 1000) + 50)

    assert rechecks == []
