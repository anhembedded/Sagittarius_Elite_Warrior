"""`EPIC-047H` - the on-demand refresh: queued, never run on the caller's thread, once per 30 s, inside the ceiling."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_work import (
    CANDLES_EVERY_S,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_facts_refresh_requests import (
    ON_DEMAND_MIN_INTERVAL_S,
    RefreshRequestVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)

from .vps_feed_world import (
    LIMIT,
    SimulatedClock,
    SimulatedSource,
    SimulatedVenue,
    drive,
    refresher_for,
)


def _booted(bots: int = 2, at_rest: tuple[str, ...] = ()):
    clock = SimulatedClock()
    venue = SimulatedVenue(clock)
    source = SimulatedSource(venue, bots)
    source.at_rest = list(at_rest)
    refresher = refresher_for(source)
    drive(refresher, clock, 1)
    return clock, venue, source, refresher


def test_a_request_is_queued_and_the_worker_reads_the_whole_round_for_that_bot() -> (
    None
):
    clock, _venue, source, refresher = _booted()
    source.calls.clear()

    answer = refresher.request("bot001")
    drive(refresher, clock, 200)

    assert answer.verdict is RefreshRequestVerdict.QUEUED
    asked = [scope for _, bot, scope in source.calls if bot == "bot001"]
    # The dear reads wait their turn behind the others' facts, but all three are read, in this order.
    assert asked[0] == "facts"
    assert [scope for scope in asked if scope != "facts"][:3] == [
        "candles",
        "planner",
        "fills",
    ]


def test_the_request_returns_before_any_read_of_the_exchange() -> None:
    _clock, _venue, source, refresher = _booted()
    reads = len(source.calls)

    refresher.request("bot001")

    assert len(source.calls) == reads


def test_a_second_request_inside_thirty_seconds_is_already_fresh_and_says_when() -> (
    None
):
    clock, _venue, source, refresher = _booted()
    refresher.request("bot001")
    drive(refresher, clock, 10)
    source.calls.clear()

    again = refresher.request("bot001")

    assert again.verdict is RefreshRequestVerdict.ALREADY_FRESH
    assert again.read_at is not None
    assert source.calls == []


def test_after_thirty_seconds_a_request_is_queued_again() -> None:
    clock, _venue, _source, refresher = _booted()
    refresher.request("bot001")
    drive(refresher, clock, ON_DEMAND_MIN_INTERVAL_S + 20)

    assert refresher.request("bot001").verdict is RefreshRequestVerdict.QUEUED


def test_a_bot_at_rest_can_be_asked_for_though_the_schedule_skips_it() -> None:
    clock, _venue, source, refresher = _booted(at_rest=("zzzstopped",))
    drive(refresher, clock, 600)
    assert [b for _, b, _ in source.calls if b == "zzzstopped"] == []

    answer = refresher.request("zzzstopped")
    drive(refresher, clock, 120)

    assert answer.verdict is RefreshRequestVerdict.QUEUED
    assert next(s for _, b, s in source.calls if b == "zzzstopped") == "facts"


def test_an_unknown_bot_and_a_refresh_that_is_off_are_told_so() -> None:
    _clock, _venue, source, refresher = _booted()
    off = refresher_for(source, VpsFeedSettings.judged(0, 3.0, True))

    assert refresher.request("nobody").verdict is RefreshRequestVerdict.UNKNOWN_BOT
    assert off.request("bot000").verdict is RefreshRequestVerdict.OFF


def test_asked_for_reads_are_counted_inside_the_ceiling() -> None:
    clock, venue, _source, refresher = _booted(bots=3)
    for _ in range(20):
        for bot in ("bot000", "bot001", "bot002"):
            refresher.request(bot)
        drive(refresher, clock, ON_DEMAND_MIN_INTERVAL_S + 1)

    assert venue.worst_window() <= int(LIMIT * 0.03)


def test_two_bots_on_one_symbol_sync_its_candles_once_and_again_after_five_minutes() -> (
    None
):
    clock, _venue, source, refresher = _booted(bots=2)
    source.calls.clear()

    refresher.request("bot000")
    refresher.request("bot001")
    drive(refresher, clock, 200)
    synced = [t for t, _bot, scope in source.calls if scope == "candles"]
    assert len(synced) == 1, "the symbol's candles are synced once, whoever asked"

    drive(refresher, clock, CANDLES_EVERY_S)
    refresher.request("bot000")
    drive(refresher, clock, 200)

    assert len([1 for _t, _b, scope in source.calls if scope == "candles"]) == 2


def test_the_candles_are_charged_their_estimate_though_the_header_never_sees_them() -> (
    None
):
    clock, venue, source, refresher = _booted(bots=1)
    source.calls.clear()
    before = len(venue.refresh_spend)

    refresher.request("bot000")
    drive(refresher, clock, 200)

    spends = venue.refresh_spend[before:]
    candles = [
        (t, w)
        for (t, w), call in zip(spends, source.calls, strict=False)
        if call[2] == "candles"
    ]
    assert candles, "the candles were synced"
    # The header cannot see the sync; the refresher still kept the next read from following it at once.
    after = [t for t, _b, s in source.calls if s != "candles" and t > candles[0][0]]
    assert after[0] - candles[0][0] >= 50 / 72 * 60 - 1.5
