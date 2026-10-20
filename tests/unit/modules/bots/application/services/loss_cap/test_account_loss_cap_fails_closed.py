"""`EPIC-026L` — the account-level loss cap fails closed: what it does when it cannot see, cannot write, or cannot stop (decision N3)."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    UnreadableBotEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    UNJUDGED_TRIP_AFTER,
    LossCapTrip,
    LossCapTripReason,
)

from .loss_cap_world import BotsWorld, MovingClock, bot, build


def _two_bots(a: str = "0", b: str = "0") -> BotsWorld:
    return BotsWorld(bot("aaa111", a), bot("bbb222", b))


def test_a_bot_with_no_price_yet_is_waited_for_and_then_trips_the_cap() -> None:
    world = build(BotsWorld(bot("aaa111", None)))
    world.sample()
    world.clock.advance(UNJUDGED_TRIP_AFTER - timedelta(seconds=1))
    world.sample()
    assert world.cap.restart_refusal() is None and world.cap.status().unjudged
    world.clock.advance(timedelta(seconds=1))
    world.sample()
    assert world.cap.restart_refusal() is not None
    assert world.events.trips[0].reason == LossCapTripReason.NOT_JUDGEABLE.value
    assert world.bots.stopped_ids == ["aaa111"]


def test_a_judged_sample_between_resets_the_wait() -> None:
    world = build(BotsWorld(bot("aaa111", None)))
    world.sample()
    world.clock.advance(UNJUDGED_TRIP_AFTER - timedelta(seconds=1))
    world.bots.set(bot("aaa111", "-5"))
    world.sample()
    world.bots.set(bot("aaa111", None))
    world.clock.advance(timedelta(seconds=30))
    world.sample()
    world.clock.advance(UNJUDGED_TRIP_AFTER - timedelta(seconds=31))
    world.sample()
    assert world.cap.restart_refusal() is None


def test_bots_that_cannot_be_read_trip_the_cap_after_the_grace_and_nothing_is_stopped_blind(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = build(_two_bots())
    world.bots.read_raises = True
    with caplog.at_level(logging.WARNING, logger="App.Bots.LossCap"):
        world.sample()
        world.clock.advance(UNJUDGED_TRIP_AFTER)
        world.sample()
    assert world.cap.restart_refusal() is not None
    assert (
        world.bots.stops == []
    )  # it could not see which bots to stop; the next sample tries again
    world.bots.read_raises = False
    world.sample()
    assert sorted(world.bots.stopped_ids) == ["aaa111", "bbb222"]


def test_a_bot_in_another_quote_asset_cannot_be_summed_so_it_is_unjudged() -> None:
    world = build(BotsWorld(bot("aaa111", "-1", symbol="BTCUSDC")))
    world.sample()
    world.clock.advance(UNJUDGED_TRIP_AFTER)
    world.sample()
    assert world.events.trips[0].reason == LossCapTripReason.NOT_JUDGEABLE.value


def test_a_refused_bot_file_is_a_bot_the_cap_cannot_judge() -> None:
    world = build(_two_bots())
    world.bots.unreadable = (
        UnreadableBotEntry("zzz999", "state/bots/zzz999.json", "bad JSON"),
    )
    world.sample()
    world.clock.advance(UNJUDGED_TRIP_AFTER)
    world.sample()
    assert "zzz999" in world.events.trips[0].detail


def test_a_stopped_bot_with_no_result_is_not_a_reason_to_trip() -> None:
    world = build(BotsWorld(bot("old222", None, state="STOPPED")))
    world.sample()
    world.clock.advance(UNJUDGED_TRIP_AFTER * 3)
    world.sample()
    assert world.cap.restart_refusal() is None


def test_a_record_that_cannot_be_written_still_trips_and_stops_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = build(_two_bots("-600", "0"))
    world.store.fails = True
    with caplog.at_level(logging.ERROR, logger="App.Bots.LossCap"):
        world.sample()
    assert world.cap.restart_refusal() is not None
    assert sorted(world.bots.stopped_ids) == ["aaa111", "bbb222"]
    assert len(world.events.trips) == 1
    assert any("a restart would forget it" in r.getMessage() for r in caplog.records)


def test_a_trip_made_by_an_unreadable_record_is_told_at_the_first_sample() -> None:
    clock = MovingClock()
    trip = LossCapTrip(
        LossCapTripReason.RECORD_UNREADABLE,
        clock.now(),
        clock.now().date(),
        None,
        "500 USDT",
        "the record cannot be read",
    )
    world = build(_two_bots(), clock=clock, found_tripped_by=trip)
    world.sample()
    world.sample()
    assert world.cap.restart_refusal() is not None
    assert [e.reason for e in world.events.trips] == ["record_unreadable"]
    assert sorted(world.bots.stopped_ids) == ["aaa111", "bbb222"]


def test_a_stop_that_raises_does_not_leave_the_other_bots_running_or_the_owner_untold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = build(BotsWorld(bot("aaa111", "-300"), bot("bbb222", "-300")))
    original = world.bots.dispatch

    def first_raises(handler_class: type, input_dto: object | None = None) -> object:
        if handler_class.__name__ == "StopBotCommand" and input_dto.bot_id == "aaa111":  # type: ignore[attr-defined]
            raise RuntimeError("the store is busy")
        return original(handler_class, input_dto)

    world.bots.dispatch = first_raises  # type: ignore[method-assign]
    with caplog.at_level(logging.ERROR, logger="App.Bots.LossCap"):
        world.sample()

    assert world.bots.stopped_ids == ["bbb222"]
    assert [e.bots_stopped for e in world.events.trips] == [1]
    assert any(
        "aaa111" in r.getMessage() and "RuntimeError" in r.getMessage()
        for r in caplog.records
    )
    world.bots.dispatch = original  # type: ignore[method-assign]
    world.sample()
    assert sorted(world.bots.stopped_ids) == ["aaa111", "bbb222"]
    assert len(world.events.trips) == 1
