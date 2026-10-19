"""`BUG-231` — a refused reduce-only order is logged with what names its cause.

The exchange refused a bot's reduce-only orders (`-2022`) at one hour and accepted them at another,
and the journal held only the exception type. The handler logs the refusal once, tagged
`[reduce-only-refused]`, with the order as sent, the account's position mode and margin type and
the exchange's own text, and the refusal still reaches the caller unchanged.
"""

from __future__ import annotations

import json
import logging
import threading
from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.reduce_only_refusal import (
    RefusedOrder,
    log_if_reduce_only_refused,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.orders.execute_order_builders import (
    make_handler,
    order_request,
)

_TAG = "[reduce-only-refused]"
_LOGGER = "App.CommandHandler"


def _refusal_line(record: logging.LogRecord) -> bool:
    """The refusal's own line, not the notes that a diagnostic read failed."""
    return record.getMessage().startswith(_TAG) and "refused on" in record.getMessage()


def _refusing(code: int, message: str) -> Mock:
    raw_client = Mock()
    raw_client.futures_create_order.side_effect = BinanceAPIException(
        None, 400, json.dumps({"code": code, "msg": message})
    )
    raw_client.futures_position_information.return_value = [
        {
            "symbol": "BTCUSDT",
            "positionAmt": "0.012",
            "entryPrice": "64000",
            "markPrice": "64100",
            "unRealizedProfit": "1.2",
            "notional": "769.2",
            "initialMargin": "153.8",
            "isolatedMargin": "153.8",
            "liquidationPrice": "52000",
        }
    ]
    return raw_client


def _close() -> ExecuteOrderCommand:
    return ExecuteOrderCommand(
        order_request=order_request(side=OrderSide.SELL, reduce_only=True),
        live=True,
        purpose=OrderPurpose.CLOSE,
    )


def _status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=MarginType.ISOLATED,
        open_position_count=1,
    )


def test_a_refused_reduce_only_order_is_logged_with_its_context_and_still_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler, _ = make_handler(
        raw_client=_refusing(-2022, "ReduceOnly Order is rejected."), status=_status()
    )

    with (
        caplog.at_level(logging.WARNING, logger=_LOGGER),
        pytest.raises(OrderRejectedByExchangeError) as refusal,
    ):
        handler.execute(_close())

    assert refusal.value.reason is OrderRejectionReason.REDUCE_ONLY_REJECTED
    (record,) = [r for r in caplog.records if _refusal_line(r)]
    text = record.getMessage()
    assert record.levelno == logging.WARNING
    assert "BTCUSDT SELL market qty=0.002" in text
    assert "reduceOnly=True" in text
    assert "positionSide=BOTH" in text
    assert "position mode=one_way" in text
    assert "position on the symbol (exchange)=0.012 margin type=isolated" in text
    assert "owner book position=no owner" in text
    assert text.startswith(_TAG)
    assert "ReduceOnly Order is rejected." in text


def test_a_diagnostic_read_that_fails_never_hides_the_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler, _ = make_handler(
        raw_client=_refusing(-2022, "ReduceOnly Order is rejected."), status=_status()
    )
    reader = handler._scopes.get(TradingVenue.FUTURES_TESTNET).ports.account_reader
    reader.check_connection.side_effect = [_status(), OSError("read failed")]

    with (
        caplog.at_level(logging.WARNING, logger=_LOGGER),
        pytest.raises(OrderRejectedByExchangeError),
    ):
        handler.execute(_close())

    (record,) = [r for r in caplog.records if _refusal_line(r)]
    assert "position mode=unreadable (OSError)" in record.getMessage()


def test_any_other_refusal_is_not_logged_as_a_reduce_only_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler, _ = make_handler(
        raw_client=_refusing(-2019, "Margin is insufficient"), status=_status()
    )

    with (
        caplog.at_level(logging.WARNING, logger=_LOGGER),
        pytest.raises(OrderRejectedByExchangeError),
    ):
        handler.execute(ExecuteOrderCommand(order_request=order_request(), live=True))

    assert [r for r in caplog.records if _TAG in r.getMessage()] == []


def test_the_owner_books_position_is_logged_beside_the_exchanges(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The engine's own figure and the exchange's, side by side, say whether they agree."""
    handler, _ = make_handler(raw_client=_refusing(-2022, "x"), status=_status())
    scope = handler._scopes.get(TradingVenue.FUTURES_TESTNET)
    client = scope.ports.client_factory.create(OrderSubmissionMode.LIVE)
    refusal = OrderRejectedByExchangeError(
        OrderRejectionReason.REDUCE_ONLY_REJECTED, "ReduceOnly Order is rejected."
    )
    order = Order(
        client_order_id=generate_client_order_id("abc123"),
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.66"),
        reduce_only=True,
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        log_if_reduce_only_refused(
            RefusedOrder(scope, client, order, refusal, Decimal("3.96"))
        )

    (record,) = [r for r in caplog.records if _refusal_line(r)]
    assert "owner book position=3.96" in record.getMessage()


def test_a_failing_position_read_never_hides_the_refusal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_client = _refusing(-2022, "ReduceOnly Order is rejected.")
    raw_client.futures_position_information.side_effect = OSError("positions down")
    handler, _ = make_handler(raw_client=raw_client, status=_status())

    with (
        caplog.at_level(logging.WARNING, logger=_LOGGER),
        pytest.raises(OrderRejectedByExchangeError) as refusal,
    ):
        handler.execute(_close())

    assert refusal.value.reason is OrderRejectionReason.REDUCE_ONLY_REJECTED
    (record,) = [r for r in caplog.records if _refusal_line(r)]
    assert (
        "position on the symbol (exchange)=unreadable (OSError)" in record.getMessage()
    )


def test_the_diagnostic_reads_run_after_the_venues_live_submission_lock_is_released() -> (
    None
):
    """The reads are network requests: while they ran under the lock, every other live order of
    the venue (a protective stop, a halt's close) waited for them. Another thread asks for the
    lock from inside each read; it must get it."""
    raw_client = _refusing(-2022, "ReduceOnly Order is rejected.")
    handler, state = make_handler(raw_client=raw_client, status=_status())
    free_during_reads: list[bool] = []

    def lock_is_free_for_another_thread() -> bool:
        answer: list[bool] = []

        def ask() -> None:
            got = state.live_submission_guard().acquire(blocking=False)
            if got:
                state.live_submission_guard().release()
            answer.append(got)

        asker = threading.Thread(target=ask)
        asker.start()
        asker.join()
        return answer[0]

    reader = handler._scopes.get(TradingVenue.FUTURES_TESTNET).ports.account_reader
    gate_check = _status()

    def check() -> ExchangeConnectionStatus:
        # The first call is the connection gate, inside the lock's caller; the one after the
        # refusal is the diagnostic read.
        if raw_client.futures_create_order.called:
            free_during_reads.append(lock_is_free_for_another_thread())
        return gate_check

    reader.check_connection.side_effect = check

    with pytest.raises(OrderRejectedByExchangeError):
        handler.execute(_close())

    assert free_during_reads == [True]
