"""`BUG-270` - what else can happen to a Futures bot while it waits under its stop.

The covered wait keeps the ladder and the stop and closes nothing, so the events a waiting bot
meets are the ones a halted-but-exposed one meets. Each is pinned here as the decision it is:

  · **a fill** is booked and its counter order is held (the ladder places nothing outside RUNNING):
    nothing is sent, the position the stop covers has grown, and the recovery attempt, which
    re-lays the ladder from the exchange's evidence, settles the rest;
  · **a user stream that goes down** does not end the wait (the stream watch acts on RUNNING and
    PAUSED bots only) but stops its resume until the stream is back;
  · **the exchange's pause met by the recovery attempt** hands the wait to the rate-limit wait
    (`EPIC-042F`): the position stays open under its stop, the ladder is re-laid when the pause
    ends, and no order is sent into the pause. A pause longer than an hour is a plain halt that
    leaves the position under its stop, as a rate limit always did on this venue, and says so.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_user_stream_status import (
    FakeUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.covered_wait_world import (
    Protection,
    a_covered_world,
    beats,
    closing_orders,
    the_feed_dies,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    attempts_of,
)

S = BotLifecycleState
D = Decimal
#: Seconds for the dwell (120 s) and the beats around it: the attempt has been made by then.
_PAST_THE_DWELL = 130


def _limited(pause: timedelta) -> ExchangeRateLimitedError:
    return ExchangeRateLimitedError(
        pause, banned=False, raw_message=f"the exchange asked for {pause}"
    )


def _waiting(monkeypatch: pytest.MonkeyPatch):
    world, marks = a_covered_world(Protection(StopCoverage.COVERED), monkeypatch)
    the_feed_dies(world, marks)
    assert world.state() is S.AWAITING_RECOVERY
    marks.unreadable = None
    return world


def test_a_fill_during_the_wait_is_booked_and_sends_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _waiting(monkeypatch)
    sent = len(world.book.requests)
    held = world.runtime().inventory
    order = world.book.open[world.open_ids_by_price()[D(110)]]

    world.fill(D(110), str(order.quantity))

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert len(world.book.requests) == sent, (
        "its counter order is held, nothing is sent"
    )
    assert world.runtime().inventory > held, "the fill is booked"


def test_a_user_stream_down_during_the_wait_does_not_end_it_but_stops_the_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stream watch halts RUNNING and PAUSED bots only, so the wait goes on under its stop; but a
    ladder must not be laid while the fills it will produce go unreported (review of PR #552, the
    same rule for a Spot wait), so the resume waits for the stream as it waits for the price."""
    stream = FakeUserStreamStatus(connected=True)
    world, marks = a_covered_world(
        Protection(StopCoverage.COVERED), monkeypatch, user_streams=stream
    )
    the_feed_dies(world, marks)
    marks.unreadable = None
    stream.connected = False
    closes_before = len(closing_orders(world))

    world.executor.facts.halt_user_stream_down(timedelta(seconds=130))
    beats(world, _PAST_THE_DWELL)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert attempts_of(world) == 0, "no attempt while the stream is down"
    assert len(closing_orders(world)) == closes_before

    stream.connected = True
    beats(world, _PAST_THE_DWELL)

    assert world.state() is S.RUNNING
    assert attempts_of(world) == 1


def test_a_pause_met_by_the_recovery_attempt_leaves_the_position_under_its_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _waiting(monkeypatch)
    closes_before = len(closing_orders(world))
    world.book.raise_next = [_limited(timedelta(seconds=60))]

    beats(world, _PAST_THE_DWELL)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert len(closing_orders(world)) == closes_before, "nothing is closed into a pause"
    assert "position stays open" in world.runtime().reason_detail


def test_a_pause_longer_than_an_hour_halts_plainly_and_leaves_the_position_under_its_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _waiting(monkeypatch)
    closes_before = len(closing_orders(world))
    world.book.raise_next = [_limited(timedelta(hours=2))]

    beats(world, _PAST_THE_DWELL)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert len(closing_orders(world)) == closes_before
    assert "position stays open" in world.runtime().reason_detail
