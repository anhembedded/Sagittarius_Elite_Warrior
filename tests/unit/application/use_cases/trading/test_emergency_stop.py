"""`EPIC-021K` §2.2 — `EmergencyStopCommandHandler`.

Same testing seam `test_execute_order.py`'s `TestLiveSubmission` already
uses: `ExchangeSessionFactory` is a `Mock` whose `create_trading_client`
returns a `Mock` raw `binance.client.Client` — `FuturesTradingClient`
itself runs for real (so the real mapper/params code is exercised), but
nothing reaches the network.

The 3-step ordering requirement (`EPIC-021K` §2.2: "thứ tự là một phần của
thiết kế") was mutation-verified manually while writing this file: swapping
`_disable_trading()` and the trading-client construction in
`EmergencyStopCommandHandler.execute()` made
`test_steps_run_in_the_mandated_order` fail, confirming the test actually
proves the order rather than merely exercising the code.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop.handler import (
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")


class _StaticMetadataProvider(IMarketMetadataProvider):
    def __init__(self, catalog: dict[str, FuturesSymbolMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> FuturesSymbolMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError


def _metadata_provider() -> IMarketMetadataProvider:
    return _StaticMetadataProvider(
        {
            "BTCUSDT": FuturesSymbolMetadata(
                symbol="BTCUSDT",
                status="TRADING",
                step_size=Decimal("0.001"),
                tick_size=Decimal("0.01"),
                min_notional=Decimal(100),
                quantity_precision=3,
                price_precision=2,
                fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
            )
        }
    )


def _open_order_payload(
    symbol: str = "BTCUSDT", client_order_id: str = "SEW-1"
) -> dict:
    return {
        "clientOrderId": client_order_id,
        "symbol": symbol,
        "side": "BUY",
        "type": "LIMIT",
        "origQty": "0.002",
        "status": "NEW",
        "price": "63000.00",
        "stopPrice": "0",
        "reduceOnly": False,
    }


def _position_payload(symbol: str = "BTCUSDT", amt: str = "0.002") -> dict:
    return {
        "symbol": symbol,
        "positionAmt": amt,
        "entryPrice": "64000.00",
        "markPrice": "64500.00",
        "unRealizedProfit": "1.00",
        "leverage": "10",
        "marginType": "cross",
        "liquidationPrice": "0",
        "updateTime": 0,
    }


def _handler(
    *,
    session_state: TradingSessionState | Mock | None = None,
    user_data_stream: Mock | None = None,
    raw_client: Mock | None = None,
) -> EmergencyStopCommandHandler:
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client or Mock()
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    return EmergencyStopCommandHandler(
        session_state if session_state is not None else TradingSessionState(),
        user_data_stream or Mock(),
        session_factory,
        credentials_provider,
        _metadata_provider(),
    )


def _quiet_raw_client() -> Mock:
    """No open orders, no positions — the common case for tests that only
    care about one step."""
    raw_client = Mock()
    raw_client.futures_get_open_orders.return_value = []
    raw_client.futures_position_information.return_value = []
    return raw_client


class TestOrdering:
    def test_steps_run_in_the_mandated_order(self) -> None:
        call_order: list[str] = []

        session_state = Mock()
        session_state.disable.side_effect = lambda: call_order.append("disable_trading")
        raw_client = Mock()

        def _record_cancel(**_kwargs):
            call_order.append("cancel_orders")
            return []

        def _record_close(**_kwargs):
            call_order.append("close_positions")
            return []

        raw_client.futures_get_open_orders.side_effect = _record_cancel
        raw_client.futures_position_information.side_effect = _record_close

        handler = _handler(session_state=session_state, raw_client=raw_client)
        handler.execute(EmergencyStopCommand())

        assert call_order == ["disable_trading", "cancel_orders", "close_positions"]

    def test_a_step_failing_does_not_stop_the_next_step_from_being_attempted(
        self,
    ) -> None:
        session_state = Mock()
        session_state.disable.side_effect = RuntimeError("boom")
        raw_client = _quiet_raw_client()

        handler = _handler(session_state=session_state, raw_client=raw_client)
        result = handler.execute(EmergencyStopCommand())

        assert result.trading_disabled.succeeded is False
        raw_client.futures_get_open_orders.assert_called_once()
        raw_client.futures_position_information.assert_called_once()


class TestDisableTrading:
    def test_disables_the_session_and_stops_the_user_data_stream(self) -> None:
        session_state = TradingSessionState()
        session_state.enable({"BTCUSDT"})
        user_data_stream = Mock()
        handler = _handler(
            session_state=session_state,
            user_data_stream=user_data_stream,
            raw_client=_quiet_raw_client(),
        )

        result = handler.execute(EmergencyStopCommand())

        assert session_state.enabled is False
        user_data_stream.stop.assert_called_once()
        assert result.trading_disabled.succeeded is True


class TestCancelAllOrders:
    def test_no_open_orders_is_a_successful_no_op(self) -> None:
        handler = _handler(raw_client=_quiet_raw_client())

        result = handler.execute(EmergencyStopCommand())

        assert result.orders_cancelled.succeeded is True
        assert "Không có lệnh" in result.orders_cancelled.detail

    def test_cancels_every_open_order_grouped_by_symbol(self) -> None:
        all_orders = [
            _open_order_payload("BTCUSDT", "SEW-1"),
            _open_order_payload("BTCUSDT", "SEW-2"),
            _open_order_payload("ETHUSDT", "SEW-3"),
        ]

        def _get_open_orders(**kwargs):
            # `FuturesTradingClient.cancel_all_orders(symbol)` re-reads
            # `get_open_orders(symbol)` internally before cancelling — see
            # that method's own docstring — so this must answer both the
            # whole-account call this handler makes and the per-symbol
            # calls made from inside each `cancel_all_orders(symbol)`.
            symbol = kwargs.get("symbol")
            if symbol is None:
                return all_orders
            return [order for order in all_orders if order["symbol"] == symbol]

        raw_client = Mock()
        raw_client.futures_get_open_orders.side_effect = _get_open_orders
        raw_client.futures_cancel_all_open_orders.return_value = {
            "code": 200,
            "msg": "ok",
        }
        raw_client.futures_position_information.return_value = []
        handler = _handler(raw_client=raw_client)

        result = handler.execute(EmergencyStopCommand())

        assert result.orders_cancelled.succeeded is True
        assert "3" in result.orders_cancelled.detail
        assert raw_client.futures_cancel_all_open_orders.call_count == 2

    def test_a_rejected_cancel_reports_partial_failure_with_a_count(self) -> None:
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = [
            _open_order_payload("BTCUSDT", "SEW-1")
        ]
        raw_client.futures_cancel_all_open_orders.side_effect = BinanceAPIException(
            None, 400, json.dumps({"code": -2011, "msg": "Unknown order"})
        )
        raw_client.futures_position_information.return_value = []
        handler = _handler(raw_client=raw_client)

        result = handler.execute(EmergencyStopCommand())

        assert result.orders_cancelled.succeeded is False
        assert "0/1" in result.orders_cancelled.detail


class TestClosePositions:
    def test_no_open_positions_is_a_successful_no_op(self) -> None:
        handler = _handler(raw_client=_quiet_raw_client())

        result = handler.execute(EmergencyStopCommand())

        assert result.positions_closed.succeeded is True
        assert "Không có vị thế" in result.positions_closed.detail

    def test_closes_a_long_position_with_a_market_sell_reduce_only_order(self) -> None:
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = []
        raw_client.futures_position_information.return_value = [
            _position_payload("BTCUSDT", amt="0.002")
        ]
        raw_client.futures_create_order.return_value = {}
        handler = _handler(raw_client=raw_client)

        result = handler.execute(EmergencyStopCommand())

        assert result.positions_closed.succeeded is True
        _, kwargs = raw_client.futures_create_order.call_args
        assert kwargs["side"] == "SELL"
        assert kwargs["type"] == "MARKET"
        assert kwargs["reduceOnly"] is True
        assert kwargs["quantity"] == "0.002"

    def test_closes_a_short_position_with_a_market_buy_reduce_only_order(self) -> None:
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = []
        raw_client.futures_position_information.return_value = [
            _position_payload("BTCUSDT", amt="-0.002")
        ]
        raw_client.futures_create_order.return_value = {}
        handler = _handler(raw_client=raw_client)

        result = handler.execute(EmergencyStopCommand())

        assert result.positions_closed.succeeded is True
        _, kwargs = raw_client.futures_create_order.call_args
        assert kwargs["side"] == "BUY"

    def test_a_failure_reports_partial_failure_not_success(self) -> None:
        """`EPIC-021K`'s own worked example — the case this VO exists for:
        a step 3 failure must never render as a plain success."""
        raw_client = Mock()
        raw_client.futures_get_open_orders.return_value = []
        raw_client.futures_position_information.return_value = [
            _position_payload("BTCUSDT", amt="0.002")
        ]
        raw_client.futures_create_order.side_effect = BinanceAPIException(
            None,
            400,
            json.dumps({"code": -2019, "msg": "Margin is insufficient"}),
        )
        handler = _handler(raw_client=raw_client)

        result = handler.execute(EmergencyStopCommand())

        assert result.positions_closed.succeeded is False
        assert result.fully_succeeded is False
        assert "0/1" in result.positions_closed.detail


class TestFullySucceeded:
    def test_true_only_when_all_three_steps_succeeded(self) -> None:
        handler = _handler(raw_client=_quiet_raw_client())

        result = handler.execute(EmergencyStopCommand())

        assert result.fully_succeeded is True
