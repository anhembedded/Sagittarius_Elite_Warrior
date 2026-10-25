"""`BUG-269` - the wait of a Futures bot that keeps its ladder under its protective stop is the one
wait in which the stop is still looked at: a stop that vanished is placed again, a stop that fired
ends the bot. Any other wait (the exchange's pause, a down stream) reads nothing, as before.

`ProtectiveStopService.supervise` asks the account first, so whether the beat reached the account is
the observable of its gate (`BotRunState.waits_for_a_quiet_feed`)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection import (
    protection_futures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protection_futures import (
    ProtectiveStopService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protective_stop_plan import (
    WantedStop,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


def _service(
    monkeypatch: pytest.MonkeyPatch, *, in_a_state_that_holds: bool, waiting: bool
) -> tuple[ProtectiveStopService, Mock]:
    monkeypatch.setattr(
        protection_futures,
        "wanted_stops",
        lambda params: (WantedStop(OrderSide.SELL, Decimal(50000)),),
    )
    context = Mock()
    context.state.holds_in.return_value = in_a_state_that_holds
    context.state.waits_for_a_quiet_feed = waiting
    context.gateway.account_reads.watched_position.return_value = None
    return ProtectiveStopService(context, Mock()), context


def test_a_bot_waiting_under_its_stop_has_its_stop_supervised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, context = _service(monkeypatch, in_a_state_that_holds=False, waiting=True)

    service.supervise()

    context.gateway.account_reads.watched_position.assert_called_once()


def test_any_other_wait_reads_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    service, context = _service(monkeypatch, in_a_state_that_holds=False, waiting=False)

    service.supervise()

    context.gateway.account_reads.watched_position.assert_not_called()
