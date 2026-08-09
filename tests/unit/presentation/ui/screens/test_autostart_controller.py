"""
Tests for AutoStartController (BOT-034 §5).

Uses a real QTimer (via `qapp`) with a tiny `fallback_seconds` rather than a
fake/injected clock — matches this codebase's existing convention for
timing-sensitive tests (see _slow_down_history_queries in
test_dev_board_async_race_conditions.py, which uses a real 0.05s
time.sleep rather than a fake clock).
"""

from Binace_Bot.src.presentation.ui.screens.dashboard.autostart_controller import (
    AutoStartController,
)

_TINY_FALLBACK_SECONDS = 0.05


def test_begin_calls_start_stream_immediately(qapp):
    calls = []
    controller = AutoStartController(
        start_stream=lambda: calls.append("start"),
        load_history=lambda: calls.append("load"),
    )

    controller.begin()

    assert calls == ["start"]


def test_begin_is_idempotent(qapp):
    calls = []
    controller = AutoStartController(
        start_stream=lambda: calls.append("start"),
        load_history=lambda: calls.append("load"),
    )

    controller.begin()
    controller.begin()

    assert calls == ["start"]


def test_a_tick_before_the_fallback_window_prevents_load_history(qtbot, qapp):
    calls = []
    controller = AutoStartController(
        start_stream=lambda: calls.append("start"),
        load_history=lambda: calls.append("load"),
        fallback_seconds=_TINY_FALLBACK_SECONDS,
    )

    controller.begin()
    controller.on_market_tick()
    qtbot.wait(int(_TINY_FALLBACK_SECONDS * 1000) + 100)

    assert calls == ["start"]


def test_no_tick_within_the_fallback_window_falls_back_to_load_history(qtbot, qapp):
    calls = []
    controller = AutoStartController(
        start_stream=lambda: calls.append("start"),
        load_history=lambda: calls.append("load"),
        fallback_seconds=_TINY_FALLBACK_SECONDS,
    )

    controller.begin()
    qtbot.wait(int(_TINY_FALLBACK_SECONDS * 1000) + 100)

    assert calls == ["start", "load"]


def test_on_market_tick_after_fallback_already_fired_is_a_safe_no_op(qtbot, qapp):
    calls = []
    controller = AutoStartController(
        start_stream=lambda: calls.append("start"),
        load_history=lambda: calls.append("load"),
        fallback_seconds=_TINY_FALLBACK_SECONDS,
    )
    controller.begin()
    qtbot.wait(int(_TINY_FALLBACK_SECONDS * 1000) + 100)

    controller.on_market_tick()  # must not raise

    assert calls == ["start", "load"]


def test_on_market_tick_before_begin_is_a_safe_no_op(qapp):
    controller = AutoStartController(
        start_stream=lambda: None,
        load_history=lambda: None,
    )

    controller.on_market_tick()  # must not raise
