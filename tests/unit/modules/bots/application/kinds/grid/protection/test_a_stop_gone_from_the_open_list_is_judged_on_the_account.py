"""`BOT-184` review - a standing stop that left the open list is told by the account as it is now,
never by the beat's position, which can be a reading shared with other bots and older than the
stop's fill; and an account that cannot be read judges nothing this beat.

`ProtectiveStopService` over the real book and the real stop; the context is the collaborator the
service reads (its gateway, state and runtime), so the three outcomes are asked of the branch
itself: flat (the stop ran), still a position (the stop is missing), unread (nothing judged)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protection_futures import (
    ProtectiveStopService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    ProtectionVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    ProtectiveStopEvent,
    ProtectiveStopState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)

_STOP_ID = "SEW-abc123-0123456789"


def _standing_stop() -> ProtectiveStop:
    stop = ProtectiveStop(_STOP_ID, OrderSide.SELL, Decimal(50000))
    for event in (ProtectiveStopEvent.ACCEPTED,):
        moved = stop.moved(event)
        assert moved is not None
        stop = moved
    assert stop.state is ProtectiveStopState.STANDING
    return stop


def _service(confirmed: Decimal | None) -> tuple[ProtectiveStopService, Mock]:
    context = Mock()
    context.state.runtime = GridRuntime(levels=()).with_stop(_standing_stop())
    context.gateway.position.return_value = confirmed
    context.gateway.account_reads.order_status.return_value = OrderStatus.FILLED
    return ProtectiveStopService(context, Mock()), context


def _absent(service: ProtectiveStopService, beat_position: Decimal):
    return service._explain_absence(_standing_stop(), beat_position)


def test_a_stop_that_ran_is_told_so_though_the_beats_reading_still_shows_a_position() -> (
    None
):
    service, _context = _service(confirmed=Decimal(0))

    assert _absent(service, Decimal("0.01")) is ProtectionVerdict.TRIGGERED


def test_a_stop_gone_over_a_position_that_still_stands_is_missing_not_triggered() -> (
    None
):
    service, context = _service(confirmed=Decimal("0.01"))

    assert _absent(service, Decimal("0.01")) is None
    (kept,) = (context.state.update.call_args.args[0].protective_stops or (None,))[:1]
    assert kept is None  # dropped to be placed again, never recorded as triggered


def test_an_account_that_cannot_be_read_judges_nothing_this_beat() -> None:
    service, context = _service(confirmed=None)

    assert _absent(service, Decimal("0.01")) is None
    context.state.update.assert_not_called()
