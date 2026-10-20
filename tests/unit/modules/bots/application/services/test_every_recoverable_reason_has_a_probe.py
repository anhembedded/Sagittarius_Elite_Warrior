"""`EPIC-042C` - the seam is locked: a reason the effective policy lets recover can be seen to clear.

A reason added to a layer without a probe would wait and tell the owner after `stalled_after`, and
never recover. This walks every effective policy of every kind on every venue and asks the Grid's
probe whether it knows each code (ADR 042 §2.2, "a test locks the seam").
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_halt_probe import (
    GridHaltProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_user_stream_status import (
    IUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_user_stream_status import (
    FakeUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    recovery_policy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_RECOVERY_LAYER,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    PRICE_FEED_STALE,
    RATE_LIMITED,
    USER_STREAM_DOWN,
    HaltCode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)


def _probe(streams: IUserStreamStatus) -> GridHaltProbe:
    world = grid_world(user_streams=streams)
    return GridHaltProbe(world.executor._context, streams, world.executor._pause)


@pytest.mark.parametrize("venue", list(TradingVenue))
def test_every_code_any_venue_lets_recover_is_one_the_grid_probe_knows(
    venue: TradingVenue,
) -> None:
    policy = recovery_policy_of(GRID_RECOVERY_LAYER, venue)
    probe = _probe(FakeUserStreamStatus())

    unknown = [row.code for row in policy.rows if not probe.knows(row.code)]

    assert unknown == []


def test_a_code_the_probe_does_not_know_never_clears() -> None:
    probe = _probe(FakeUserStreamStatus(connected=True))

    assert not probe.knows(HaltCode("order_rejected"))
    assert probe.is_clear(HaltCode("order_rejected"), 0.0) is False


def test_the_stream_reason_clears_with_the_stream_and_the_price_reason_needs_a_tick() -> (
    None
):
    streams = FakeUserStreamStatus(connected=False)
    probe = _probe(streams)

    assert probe.is_clear(USER_STREAM_DOWN, 0.0) is False
    streams.connected = True
    assert probe.is_clear(USER_STREAM_DOWN, 0.0) is True
    assert probe.is_clear(PRICE_FEED_STALE, 0.0) is False, "no tick was ever heard"


def test_the_rate_limit_reason_is_clear_until_a_pause_is_met_and_again_when_it_ends() -> (
    None
):
    """`EPIC-042F`: *clear* is the pause's end, not a tick or a stream, so a bot that met none has
    nothing to wait for (a quiet feed's wait must not be held by a pause that never was)."""
    world = grid_world()
    probe = _probe(FakeUserStreamStatus())
    assert probe.is_clear(RATE_LIMITED, 0.0) is True, "no pause was ever met"

    world.book.raise_next = [
        ExchangeRateLimitedError(
            timedelta(seconds=60), banned=False, raw_message="slow down"
        )
    ]
    world.executor.start()
    held = GridHaltProbe(
        world.executor._context, FakeUserStreamStatus(), world.executor._pause
    )
    assert held.is_clear(RATE_LIMITED, 0.0) is False
    world.monotonic.advance(59)
    assert held.is_clear(RATE_LIMITED, 0.0) is False
    world.monotonic.advance(1)
    assert held.is_clear(RATE_LIMITED, 0.0) is True
