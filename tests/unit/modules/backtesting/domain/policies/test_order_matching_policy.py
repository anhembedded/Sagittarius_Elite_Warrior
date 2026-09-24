from __future__ import annotations

from dataclasses import dataclass

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.order_matching_policy import (
    OrderMatchingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@dataclass
class _FakeStoppablePosition:
    side: PositionSide
    stop_loss_price: float | None = None
    take_profit_price: float | None = None


@pytest.fixture
def policy() -> OrderMatchingPolicy:
    return OrderMatchingPolicy()


def test_slippage_delta_calculation(policy: OrderMatchingPolicy):
    # 5 ticks * 0.01 tick_size = 0.05
    assert policy.calculate_slippage_delta(5, 0.01) == pytest.approx(0.05)
    assert policy.calculate_slippage_delta(0, 0.01) == 0.0


def test_entry_and_exit_effective_price_with_slippage(policy: OrderMatchingPolicy):
    slippage = 0.5

    # LONG entry buys higher, exit sells lower
    assert (
        policy.calculate_entry_effective_price(PositionSide.LONG, 100.0, slippage)
        == 100.5
    )
    assert (
        policy.calculate_exit_effective_price(PositionSide.LONG, 100.0, slippage)
        == 99.5
    )

    # SHORT entry sells lower, exit covers higher
    assert (
        policy.calculate_entry_effective_price(PositionSide.SHORT, 100.0, slippage)
        == 99.5
    )
    assert (
        policy.calculate_exit_effective_price(PositionSide.SHORT, 100.0, slippage)
        == 100.5
    )

    # Extreme slippage clamping to 0.0
    assert policy.calculate_entry_effective_price(PositionSide.SHORT, 10.0, 15.0) == 0.0
    assert policy.calculate_exit_effective_price(PositionSide.LONG, 10.0, 15.0) == 0.0


def test_stop_loss_and_take_profit_price_calculation(policy: OrderMatchingPolicy):
    # If pct is None, returns None
    assert policy.calculate_stop_loss_price(PositionSide.LONG, 100.0, None) is None
    assert policy.calculate_take_profit_price(PositionSide.LONG, 100.0, None) is None

    # LONG: SL is 5% below (95.0), TP is 10% above (110.0)
    assert policy.calculate_stop_loss_price(
        PositionSide.LONG, 100.0, 5.0
    ) == pytest.approx(95.0)
    assert policy.calculate_take_profit_price(
        PositionSide.LONG, 100.0, 10.0
    ) == pytest.approx(110.0)

    # SHORT: SL is 5% above (105.0), TP is 10% below (90.0)
    assert policy.calculate_stop_loss_price(
        PositionSide.SHORT, 100.0, 5.0
    ) == pytest.approx(105.0)
    assert policy.calculate_take_profit_price(
        PositionSide.SHORT, 100.0, 10.0
    ) == pytest.approx(90.0)


def test_evaluate_intrabar_stops_long_single_hits(policy: OrderMatchingPolicy):
    pos = _FakeStoppablePosition(
        side=PositionSide.LONG,
        stop_loss_price=95.0,
        take_profit_price=110.0,
    )

    # Bar touches low 94.0 -> SL hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=105.0, low=94.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 95.0, ExitReason.STOP_LOSS)
    assert still_open == []

    # Bar touches high 112.0 -> TP hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=112.0, low=98.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 110.0, ExitReason.TAKE_PROFIT)
    assert still_open == []


def test_evaluate_intrabar_stops_short_single_hits(policy: OrderMatchingPolicy):
    pos = _FakeStoppablePosition(
        side=PositionSide.SHORT,
        stop_loss_price=105.0,
        take_profit_price=90.0,
    )

    # Bar touches high 106.0 -> SL hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=106.0, low=95.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 105.0, ExitReason.STOP_LOSS)
    assert still_open == []

    # Bar touches low 89.0 -> TP hit
    triggered, still_open = policy.evaluate_intrabar_stops([pos], high=102.0, low=89.0)
    assert len(triggered) == 1
    assert triggered[0] == (pos, 90.0, ExitReason.TAKE_PROFIT)
    assert still_open == []


def test_evaluate_intrabar_stops_tie_breaker_stop_loss_wins(
    policy: OrderMatchingPolicy,
):
    # Long position where bar touches both SL (95.0) and TP (110.0)
    long_pos = _FakeStoppablePosition(
        side=PositionSide.LONG,
        stop_loss_price=95.0,
        take_profit_price=110.0,
    )
    triggered, _ = policy.evaluate_intrabar_stops([long_pos], high=115.0, low=90.0)
    assert len(triggered) == 1
    assert triggered[0][2] == ExitReason.STOP_LOSS

    # Short position where bar touches both SL (105.0) and TP (90.0)
    short_pos = _FakeStoppablePosition(
        side=PositionSide.SHORT,
        stop_loss_price=105.0,
        take_profit_price=90.0,
    )
    triggered, _ = policy.evaluate_intrabar_stops([short_pos], high=115.0, low=85.0)
    assert len(triggered) == 1
    assert triggered[0][2] == ExitReason.STOP_LOSS


# ---------------------------------------------------------------------------
# BOT-105B — bar magnifier conflict resolution
# ---------------------------------------------------------------------------


def test_magnifier_lookup_is_not_called_when_the_bar_is_not_ambiguous(
    policy: OrderMatchingPolicy,
):
    """A bar that only hits one threshold must never pay a magnifier query —
    proves the lookup is conditional on genuine ambiguity, not called
    unconditionally whenever one is supplied."""
    pos = _FakeStoppablePosition(
        side=PositionSide.LONG, stop_loss_price=95.0, take_profit_price=110.0
    )
    calls: list[None] = []

    def lookup() -> list[tuple[float, float]]:
        calls.append(None)
        return [(112.0, 108.0)]

    triggered, still_open = policy.evaluate_intrabar_stops(
        [pos], high=106.0, low=100.0, magnifier_lookup=lookup
    )
    assert triggered == []
    assert still_open == [pos]
    assert calls == []


def test_magnifier_resolves_take_profit_first_from_chronological_sub_candles(
    policy: OrderMatchingPolicy,
):
    """Mutation-sensitive: sub-candle 1 only crosses TP, sub-candle 2 (never
    reached if the walk is correct) only crosses SL. A policy that scanned
    the whole magnifier sequence instead of stopping at the first resolving
    sub-candle, or that checked sub-candles out of order, would wrongly
    return STOP_LOSS here."""
    pos = _FakeStoppablePosition(
        side=PositionSide.LONG, stop_loss_price=95.0, take_profit_price=105.0
    )
    sub_candles = [(108.0, 99.0), (100.0, 90.0)]

    triggered, still_open = policy.evaluate_intrabar_stops(
        [pos], high=115.0, low=90.0, magnifier_lookup=lambda: sub_candles
    )
    assert triggered == [(pos, 105.0, ExitReason.TAKE_PROFIT)]
    assert still_open == []


def test_magnifier_resolves_stop_loss_first_from_chronological_sub_candles(
    policy: OrderMatchingPolicy,
):
    """Mirror of the take-profit case, proving the magnifier path (not just
    the pessimistic default, which would also say STOP_LOSS) actually ran —
    verified via the lookup call count."""
    pos = _FakeStoppablePosition(
        side=PositionSide.LONG, stop_loss_price=95.0, take_profit_price=105.0
    )
    sub_candles = [(100.0, 93.0), (110.0, 90.0)]
    calls: list[None] = []

    def lookup() -> list[tuple[float, float]]:
        calls.append(None)
        return sub_candles

    triggered, _ = policy.evaluate_intrabar_stops(
        [pos], high=115.0, low=90.0, magnifier_lookup=lookup
    )
    assert triggered == [(pos, 95.0, ExitReason.STOP_LOSS)]
    assert len(calls) == 1


def test_magnifier_resolves_short_position_take_profit_first(
    policy: OrderMatchingPolicy,
):
    """SHORT mirrors LONG's high/low roles: TP sits below entry, SL above."""
    pos = _FakeStoppablePosition(
        side=PositionSide.SHORT, stop_loss_price=105.0, take_profit_price=95.0
    )
    # Sub-candle 1 dips to TP (95.0) without rising to SL (105.0); sub-candle
    # 2, never reached if correct, would hit SL.
    sub_candles = [(100.0, 92.0), (110.0, 96.0)]

    triggered, _ = policy.evaluate_intrabar_stops(
        [pos], high=115.0, low=90.0, magnifier_lookup=lambda: sub_candles
    )
    assert triggered == [(pos, 95.0, ExitReason.TAKE_PROFIT)]


def test_magnifier_falls_back_to_pessimistic_when_lookup_returns_no_data(
    policy: OrderMatchingPolicy,
):
    """The symbol/resolution was never separately synced (task §2.1's own
    documented fallback) — must not crash, and must keep the BOT-041
    pessimistic default rather than silently opening the position further."""
    pos = _FakeStoppablePosition(
        side=PositionSide.LONG, stop_loss_price=95.0, take_profit_price=105.0
    )
    triggered, _ = policy.evaluate_intrabar_stops(
        [pos], high=115.0, low=90.0, magnifier_lookup=list
    )
    assert triggered == [(pos, 95.0, ExitReason.STOP_LOSS)]


def test_magnifier_falls_back_to_pessimistic_when_finest_sub_candle_still_ambiguous(
    policy: OrderMatchingPolicy,
):
    """Even the finest available sub-candle still straddles both
    thresholds — a real ambiguity at that resolution, not a lookup failure —
    so the walk exhausts its sequence and lands on the same pessimistic
    default."""
    pos = _FakeStoppablePosition(
        side=PositionSide.LONG, stop_loss_price=95.0, take_profit_price=105.0
    )
    sub_candles = [(108.0, 92.0)]  # this single sub-candle also hits both

    triggered, _ = policy.evaluate_intrabar_stops(
        [pos], high=115.0, low=90.0, magnifier_lookup=lambda: sub_candles
    )
    assert triggered == [(pos, 95.0, ExitReason.STOP_LOSS)]


def test_magnifier_lookup_is_memoized_across_positions_in_the_same_bar(
    policy: OrderMatchingPolicy,
):
    """Two positions ambiguous on the same bar share one magnifier fetch —
    proves the lazy lookup is called at most once per `evaluate_intrabar_stops()`
    invocation, not once per ambiguous position."""
    pos_a = _FakeStoppablePosition(
        side=PositionSide.LONG, stop_loss_price=95.0, take_profit_price=105.0
    )
    pos_b = _FakeStoppablePosition(
        side=PositionSide.LONG, stop_loss_price=94.0, take_profit_price=106.0
    )
    calls: list[None] = []

    def lookup() -> list[tuple[float, float]]:
        calls.append(None)
        return [(108.0, 99.0)]

    policy.evaluate_intrabar_stops(
        [pos_a, pos_b], high=115.0, low=90.0, magnifier_lookup=lookup
    )
    assert len(calls) == 1
