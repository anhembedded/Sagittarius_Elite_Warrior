"""`EPIC-026L` — the account-level loss cap: it trips at the figure, stops every bot through the Stop,
stays tripped until the owner acknowledges, and fails closed when it cannot judge (decision N3)."""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    LossCapTripReason,
)

from .loss_cap_world import BotsWorld, CapWorld, bot, build


def _two_bots(a: str = "0", b: str = "0") -> BotsWorld:
    return BotsWorld(bot("aaa111", a), bot("bbb222", b))


def _tripped() -> CapWorld:
    world = build(_two_bots())
    world.sample()
    world.bots.set(bot("aaa111", "-300"))
    world.bots.set(bot("bbb222", "-200"))
    world.sample()
    return world


# --- the figure ---


def test_a_loss_one_cent_below_the_figure_trips_nothing() -> None:
    world = build(_two_bots("-300", "-199.99"))
    world.sample()
    assert world.cap.restart_refusal() is None
    assert world.bots.stops == []
    assert world.events.trips == []


def test_a_loss_exactly_at_the_figure_trips_and_the_sum_is_over_every_bot() -> None:
    world = _tripped()
    assert world.cap.restart_refusal() is not None
    assert sorted(world.bots.stopped_ids) == ["aaa111", "bbb222"]


def test_a_gain_in_one_bot_offsets_a_loss_in_another() -> None:
    world = build(_two_bots("-400", "250"))
    world.sample()
    assert world.cap.restart_refusal() is None


def test_the_trip_tells_the_owner_once_with_the_figure_the_loss_and_the_count() -> None:
    world = _tripped()
    world.sample()
    world.sample()
    (event,) = world.events.trips
    assert event.reason == LossCapTripReason.LOSS_REACHED.value
    assert event.figure == "500 USDT"
    assert Decimal(event.loss) == Decimal(500)
    assert event.bots_stopped == 2


# --- the stop ---


def test_only_bots_that_are_not_at_rest_are_stopped() -> None:
    world = build(
        BotsWorld(
            bot("run111", "-600"),
            bot("old222", "0", state="STOPPED"),
            bot("new333", None, state="DRAFT"),
        )
    )
    world.sample()
    assert world.bots.stopped_ids == ["run111"]


def test_a_spot_bot_is_stopped_keeping_its_base_and_a_futures_bot_closes_its_position() -> (
    None
):
    world = build(
        BotsWorld(
            bot("spot11", "-300"),
            bot("fut222", "-300", venue="futures_mainnet", symbol="ETHUSDT"),
        )
    )
    world.sample()
    assert dict(world.bots.stops) == {
        "spot11": ExposureHandling.KEEP,
        "fut222": ExposureHandling.CLOSE_AT_MARKET,
    }


def test_the_trip_is_recorded_before_the_first_stop_is_asked() -> None:
    """A crash between the two must leave a record that holds every bot down."""
    world = build(_two_bots("-600", "0"))
    seen: list[bool] = []
    original = world.bots.dispatch

    def spy(handler_class: type, input_dto: object | None = None) -> object:
        if handler_class.__name__ == "StopBotCommand":
            seen.append(
                world.store.record is not None and world.store.record.trip is not None
            )
        return original(handler_class, input_dto)

    world.bots.dispatch = spy  # type: ignore[method-assign]
    world.sample()
    assert seen and all(seen)


def test_a_bot_the_stop_refuses_is_asked_again_by_the_next_sample_and_told_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = build(_two_bots("-600", "0"))
    world.bots.refuse["aaa111"] = "no stop from this state"
    with caplog.at_level(logging.WARNING, logger="App.Bots.LossCap"):
        world.sample()
        world.sample()
        world.sample()
    refused = [r for r in caplog.records if "was not stopped" in r.getMessage()]
    assert len(refused) == 1
    del world.bots.refuse["aaa111"]
    world.sample()
    assert "aaa111" in world.bots.stopped_ids


def test_a_bot_that_gets_going_while_tripped_is_stopped_again_by_the_next_sample() -> (
    None
):
    world = _tripped()
    world.bots.set(bot("aaa111", "-300", state="RUNNING"))
    before = world.bots.stopped_ids.count("aaa111")
    world.sample()
    assert world.bots.stopped_ids.count("aaa111") == before + 1
    assert len(world.events.trips) == 1


def test_a_bot_already_stopping_is_not_asked_again() -> None:
    world = _tripped()
    count = len(world.bots.stops)
    world.sample()
    assert len(world.bots.stops) == count


# --- staying tripped ---


def test_a_tripped_cap_refuses_a_restart_in_words_that_name_the_acknowledgement() -> (
    None
):
    sentence = _tripped().cap.restart_refusal()
    assert sentence is not None and "loss-cap-ack" in sentence and "tripped" in sentence


def test_the_trip_survives_a_restart_and_stops_what_the_restart_brought_back() -> None:
    world = _tripped()
    world.bots.set(bot("aaa111", "-300", state="RECOVERING"))
    world.bots.set(bot("bbb222", "-200", state="RECOVERING"))
    after = world.restart()
    assert after.cap.restart_refusal() is not None
    after.sample()
    assert (
        after.bots.stopped_ids.count("aaa111") == 2
    )  # once before, once after the restart
    assert len(after.events.trips) == 0  # the owner was told when it happened


def test_the_trip_survives_a_day_roll_over() -> None:
    world = _tripped()
    world.clock.advance(timedelta(days=1))
    world.sample()
    assert world.cap.restart_refusal() is not None


def test_removing_the_figure_is_not_an_acknowledgement() -> None:
    world = _tripped().restart(figure=None)
    assert world.cap.restart_refusal() is not None
    world.bots.set(bot("aaa111", "-300", state="RUNNING"))
    world.sample()
    assert world.bots.bots["aaa111"].state == "STOPPING"


# --- the acknowledgement ---


def test_an_acknowledgement_lets_bots_start_again_and_starts_none() -> None:
    world = _tripped()
    stops = len(world.bots.stops)
    assert world.cap.acknowledge() is True
    assert world.cap.restart_refusal() is None
    assert len(world.bots.stops) == stops


def test_acknowledging_a_cap_that_is_not_tripped_changes_nothing() -> None:
    world = build(_two_bots())
    assert world.cap.acknowledge() is False


def test_the_acknowledged_loss_is_not_counted_again_but_the_next_figure_s_worth_trips() -> (
    None
):
    world = _tripped()
    world.cap.acknowledge()
    world.bots.set(bot("aaa111", "-300"))
    world.bots.set(bot("bbb222", "-200"))
    world.sample()
    assert world.cap.restart_refusal() is None  # the 500 already lost is accepted
    world.bots.set(bot("aaa111", "-300"))
    world.bots.set(bot("bbb222", "-700"))
    world.sample()
    assert world.cap.restart_refusal() is not None
    assert len(world.events.trips) == 2


def test_the_acknowledgement_is_recorded_so_a_restart_does_not_bring_the_trip_back() -> (
    None
):
    world = _tripped()
    world.cap.acknowledge()
    assert world.restart().cap.restart_refusal() is None


# --- the day ---


def test_what_was_lost_before_midnight_is_not_counted_after_it() -> None:
    world = build(_two_bots("-400", "0"))
    world.sample()
    world.clock.advance(timedelta(hours=16))  # 01:00 the next day
    world.bots.set(bot("aaa111", "-450"))
    world.sample()
    assert world.cap.restart_refusal() is None
    assert world.cap.status().day == "2026-10-21"


def test_a_bot_that_began_the_day_with_an_old_loss_does_not_bring_it_into_the_day() -> (
    None
):
    world = build(BotsWorld(bot("aaa111", "-9000", run=None)))
    world.sample()
    assert world.cap.restart_refusal() is None


# --- the cap off ---


def test_with_no_figure_the_cap_judges_nothing_and_writes_nothing() -> None:
    world = build(_two_bots("-9000", "-9000"), figure=None)
    world.sample()
    assert world.cap.restart_refusal() is None
    assert world.bots.stops == [] and world.store.writes == []
    assert world.cap.status().figure is None and not world.cap.status().unjudged


def test_the_status_says_the_figure_the_day_s_result_and_the_trip() -> None:
    world = _tripped()
    status = world.cap.status()
    assert status.figure == "500 USDT" and status.tripped
    assert status.day_pnl == Decimal(-500)
    assert status.trip_reason == "loss_reached"
