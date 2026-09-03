from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)


def test_starts_disabled_with_no_known_positions() -> None:
    state = TradingSessionState()
    assert state.enabled is False
    assert state.orders_sent_this_session == 0
    assert state.open_position_count("BTCUSDT") == 0


def test_enable_seeds_known_open_symbols_from_reconciliation() -> None:
    state = TradingSessionState()
    state.enable({"BTCUSDT"})
    assert state.enabled is True
    assert state.open_position_count("BTCUSDT") == 1
    assert state.open_position_count("ETHUSDT") == 0


def test_disable_turns_off_without_forgetting_reconciled_positions() -> None:
    state = TradingSessionState()
    state.enable({"BTCUSDT"})
    state.disable()
    assert state.enabled is False
    assert state.open_position_count("BTCUSDT") == 1


def test_record_order_sent_increments_counter_and_marks_symbol_open() -> None:
    state = TradingSessionState()
    now = datetime(2026, 8, 27, tzinfo=UTC)

    state.record_order_sent("BTCUSDT", now)

    assert state.orders_sent_this_session == 1
    assert state.open_position_count("BTCUSDT") == 1


def test_time_since_last_order_is_none_before_any_order() -> None:
    state = TradingSessionState()
    assert (
        state.time_since_last_order("BTCUSDT", datetime(2026, 8, 27, tzinfo=UTC))
        is None
    )


def test_time_since_last_order_reflects_the_recorded_time() -> None:
    state = TradingSessionState()
    first = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
    state.record_order_sent("BTCUSDT", first)

    later = first + timedelta(seconds=90)
    assert state.time_since_last_order("BTCUSDT", later) == timedelta(seconds=90)


def test_generation_advances_on_every_state_change() -> None:
    """`BUG-088` — `enable()`'s `expected_generation` guard is only
    meaningful if every mutation bumps it: `disable()`, `record_order_sent()`
    and `reconcile_position()` too, not just `enable()` itself."""
    state = TradingSessionState()
    start = state.generation

    state.enable(set())
    assert state.generation == start + 1

    state.disable()
    assert state.generation == start + 2

    state.record_order_sent("BTCUSDT", datetime(2026, 8, 27, tzinfo=UTC))
    assert state.generation == start + 3

    state.reconcile_position("ETHUSDT", has_position=True)
    assert state.generation == start + 4


def test_enable_with_a_stale_expected_generation_does_not_apply() -> None:
    state = TradingSessionState()
    stale = state.generation
    state.disable()  # bumps the generation past `stale`

    applied = state.enable({"BTCUSDT"}, expected_generation=stale)

    assert applied is False
    assert state.enabled is False
    assert state.known_open_symbols == set()


def test_enable_with_the_current_expected_generation_applies() -> None:
    state = TradingSessionState()
    current = state.generation

    applied = state.enable({"BTCUSDT"}, expected_generation=current)

    assert applied is True
    assert state.enabled is True
    assert state.known_open_symbols == {"BTCUSDT"}


def test_reconcile_position_reports_disagreement_and_updates_membership() -> None:
    state = TradingSessionState()

    disagreed_on_open = state.reconcile_position("BTCUSDT", has_position=True)
    assert disagreed_on_open is True
    assert state.open_position_count("BTCUSDT") == 1

    agreed = state.reconcile_position("BTCUSDT", has_position=True)
    assert agreed is False

    disagreed_on_close = state.reconcile_position("BTCUSDT", has_position=False)
    assert disagreed_on_close is True
    assert state.open_position_count("BTCUSDT") == 0
