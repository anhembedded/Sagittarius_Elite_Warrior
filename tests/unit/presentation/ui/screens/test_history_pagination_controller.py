"""Tests for HistoryPaginationController (BOT-035)."""

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
    calls = []
    controller = HistoryPaginationController(
        fetch_older=lambda s, t: calls.append((s, t))
    )
    controller.on_near_left_edge("ETHUSDT", 1000.0)

    controller.on_load_more_finished("ETHUSDT")
    controller.on_near_left_edge("ETHUSDT", 900.0)

    assert calls == [("ETHUSDT", 1000.0), ("ETHUSDT", 900.0)]


def test_on_load_more_finished_for_a_symbol_never_in_flight_is_a_safe_no_op(qapp):
    controller = HistoryPaginationController(fetch_older=lambda s, t: None)

    controller.on_load_more_finished("ETHUSDT")  # must not raise
