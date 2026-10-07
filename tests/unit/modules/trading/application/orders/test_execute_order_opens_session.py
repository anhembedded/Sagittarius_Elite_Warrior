"""`EPIC-034C` — a manual live order opens the order session itself, and only a
manual one does.

@details The switch that used to be turned on first is gone; placing an order is
the deliberate action. It reconciles the account before anything is sent
(`SessionReadiness`), refuses a foreign position with the words the switch used
and sends nothing, and an automated order never reopens a session Emergency
Stop closed.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)


def _raw_client(positions: list[dict] | None = None) -> Mock:
    raw_client = Mock()
    raw_client.futures_create_order.return_value = {}
    raw_client.futures_position_information.return_value = positions or []
    raw_client.futures_get_open_orders.return_value = []
    raw_client.futures_get_open_algo_orders.return_value = []
    return raw_client


def _foreign_position() -> dict:
    return {
        "symbol": "ETHUSDT",
        "positionAmt": "1",
        "entryPrice": "3000",
        "markPrice": "3010",
        "unRealizedProfit": "10",
        "notional": "3010",
        "initialMargin": "301",
        "isolatedMargin": "0",
        "liquidationPrice": "2000",
    }


def test_a_manual_live_order_opens_a_closed_session_and_is_sent() -> None:
    raw_client = _raw_client()
    handler, state = make_handler(enabled=False, raw_client=raw_client)
    assert state.enabled is False

    result = handler.execute(
        ExecuteOrderCommand(
            order_request=order_request(), live=True, opens_session=True
        )
    )

    assert result.blocked_by is None
    assert result.submitted_order is not None
    assert state.enabled is True
    raw_client.futures_create_order.assert_called_once()


def test_a_foreign_position_refuses_the_manual_order_and_sends_nothing() -> None:
    raw_client = _raw_client([_foreign_position()])
    handler, state = make_handler(enabled=False, raw_client=raw_client)

    result = handler.execute(
        ExecuteOrderCommand(
            order_request=order_request(), live=True, opens_session=True
        )
    )

    assert result.blocked_by is SessionBlockReason.UNEXPECTED_POSITIONS
    assert result.preview is None
    assert state.enabled is False
    raw_client.futures_create_order.assert_not_called()


def test_an_automated_order_never_reopens_a_closed_session() -> None:
    """What an Emergency Stop closed stays closed: a bot's or a strategy's late
    order reaches the gate, not the reconciliation."""
    raw_client = _raw_client()
    handler, state = make_handler(enabled=False, raw_client=raw_client)

    result = handler.execute(
        ExecuteOrderCommand(order_request=order_request(), live=True)
    )

    assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
    assert state.enabled is False
    raw_client.futures_position_information.assert_not_called()
    raw_client.futures_create_order.assert_not_called()


def test_a_dry_run_does_not_open_the_session() -> None:
    handler, state = make_handler(enabled=False, raw_client=_raw_client())

    result = handler.execute(
        ExecuteOrderCommand(order_request=order_request(), opens_session=True)
    )

    assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
    assert state.enabled is False


def test_an_open_session_is_not_reconciled_again_by_the_next_manual_order() -> None:
    """The first order's position would refuse the second if it were."""
    raw_client = _raw_client()
    handler, state = make_handler(enabled=False, raw_client=raw_client)
    handler.execute(
        ExecuteOrderCommand(
            order_request=order_request(), live=True, opens_session=True
        )
    )
    raw_client.futures_position_information.reset_mock()
    raw_client.futures_position_information.return_value = [_foreign_position()]

    second = handler.execute(
        ExecuteOrderCommand(
            order_request=order_request(symbol="BTCUSDT"),
            live=True,
            opens_session=True,
        )
    )

    assert state.enabled is True
    assert second.blocked_by is not SessionBlockReason.UNEXPECTED_POSITIONS
    raw_client.futures_position_information.assert_not_called()


def test_an_order_refused_for_its_own_terms_opens_nothing() -> None:
    """The preview's refusals cost nothing, so they come before the
    reconciliation: a refused order starts no stream and resumes no bot."""
    raw_client = _raw_client()
    handler, state = make_handler(enabled=False, raw_client=raw_client)

    result = handler.execute(
        ExecuteOrderCommand(
            order_request=order_request(quantity=Decimal("0.000001")),
            live=True,
            opens_session=True,
        )
    )

    assert result.blocked_by is ExecuteOrderNotionalRejection.MIN_NOTIONAL
    assert state.enabled is False
    raw_client.futures_position_information.assert_not_called()


def test_an_order_on_a_symbol_leased_to_another_owner_opens_nothing() -> None:
    raw_client = _raw_client()
    handler, state = make_handler(enabled=False, raw_client=raw_client)
    state.claim_symbol("BTCUSDT", "strategy")

    result = handler.execute(
        ExecuteOrderCommand(
            order_request=order_request(), live=True, opens_session=True
        )
    )

    assert result.blocked_by is ExecuteOrderSafetyGate.SYMBOL_LEASED
    assert state.enabled is False
    raw_client.futures_position_information.assert_not_called()
