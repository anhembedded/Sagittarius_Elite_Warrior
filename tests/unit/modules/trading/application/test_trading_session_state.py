from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
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

    state.record_order_sent("BTCUSDT", now, venue_has_positions=True)

    assert state.orders_sent_this_session == 1
    assert state.open_position_count("BTCUSDT") == 1


def test_record_order_sent_on_a_venue_without_positions_counts_but_does_not_mark_open() -> (
    None
):
    """`BUG-142` — Spot has no positions, so nothing would ever clear the mark."""
    state = TradingSessionState()
    now = datetime(2026, 8, 27, tzinfo=UTC)

    state.record_order_sent("BTCUSDT", now, venue_has_positions=False)

    assert state.orders_sent_this_session == 1
    assert state.open_position_count("BTCUSDT") == 0
    assert state.time_since_last_order("BTCUSDT", now) == timedelta(0)


def test_time_since_last_order_is_none_before_any_order() -> None:
    state = TradingSessionState()
    assert (
        state.time_since_last_order("BTCUSDT", datetime(2026, 8, 27, tzinfo=UTC))
        is None
    )


def test_time_since_last_order_reflects_the_recorded_time() -> None:
    state = TradingSessionState()
    first = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
    state.record_order_sent("BTCUSDT", first, venue_has_positions=True)

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

    state.record_order_sent(
        "BTCUSDT", datetime(2026, 8, 27, tzinfo=UTC), venue_has_positions=True
    )
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


def test_spot_baseline_holdings_is_none_before_any_enable() -> None:
    """`EPIC-027M` — the "unknown baseline" case `EmergencyStopCommandHandler`
    must treat as "refuse to sell anything on Spot", not as an empty
    baseline (which would mean "sell everything")."""
    state = TradingSessionState()
    assert state.spot_baseline_holdings() is None


def test_enable_records_the_spot_baseline_when_given() -> None:
    state = TradingSessionState()
    state.enable(set(), spot_baseline_holdings={"BTC": Decimal("0.5")})
    assert state.spot_baseline_holdings() == {"BTC": Decimal("0.5")}


def test_enable_with_no_spot_baseline_argument_clears_a_previous_one() -> None:
    """A Futures/`DISABLED` enable passes no baseline — this must not leave
    a prior Spot session's baseline behind for a later, unrelated session
    to misapply."""
    state = TradingSessionState()
    state.enable(set(), spot_baseline_holdings={"BTC": Decimal("0.5")})

    state.enable(set())

    assert state.spot_baseline_holdings() is None


def test_enable_records_an_empty_spot_baseline_distinctly_from_none() -> None:
    """Enabling while holding literally nothing is a real, distinct
    baseline (`{}`) — every unit later held is then fair game to sell,
    unlike `None` ("never enabled"), which must refuse to sell anything."""
    state = TradingSessionState()
    state.enable(set(), spot_baseline_holdings={})
    assert state.spot_baseline_holdings() == {}
    assert state.spot_baseline_holdings() is not None


def test_spot_baseline_holdings_returns_a_copy_not_the_live_dict() -> None:
    """Same discipline as `read_all()`'s tuple copy of `known_open_symbols`
    — handing out the live dict would let a caller mutate session state by
    accident."""
    state = TradingSessionState()
    state.enable(set(), spot_baseline_holdings={"BTC": Decimal("0.5")})

    baseline = state.spot_baseline_holdings()
    assert baseline is not None
    baseline["BTC"] = Decimal(999)

    assert state.spot_baseline_holdings() == {"BTC": Decimal("0.5")}


def test_a_stale_expected_generation_does_not_apply_the_spot_baseline() -> None:
    """`BUG-088`'s same conditional-apply guard must cover the baseline
    too — a superseded `enable()` call must not silently record a stale
    baseline any more than it silently turns trading on."""
    state = TradingSessionState()
    stale_generation = state.generation
    state.disable()  # bumps generation, making `stale_generation` stale

    applied = state.enable(
        set(),
        expected_generation=stale_generation,
        spot_baseline_holdings={"BTC": Decimal("0.5")},
    )

    assert applied is False
    assert state.spot_baseline_holdings() is None
