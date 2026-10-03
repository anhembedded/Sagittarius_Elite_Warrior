from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.enable_trading import (
    EnableTradingCommand,
    EnableTradingCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")


def _ready_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
    )


def _position_payload(symbol: str = "BTCUSDT") -> dict:
    # `BUG-114` — real `/fapi/v3/positionRisk` carries no `leverage`/
    # `marginType` field; `notional`/`initialMargin`/`isolatedMargin` are
    # what the mapper actually derives them from now (see
    # `futures_order_payload_mapper.py`). Not asserted in this file.
    return {
        "symbol": symbol,
        "positionAmt": "0.5",
        "entryPrice": "60000",
        "markPrice": "60100",
        "unRealizedProfit": "50",
        "notional": "30050",
        "initialMargin": "3005",
        "isolatedMargin": "0",
        "liquidationPrice": "45000",
    }


def _handler(
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    status: ExchangeConnectionStatus | None = None,
    position_payloads: list[dict] | None = None,
    open_order_payloads: list[dict] | None = None,
    algo_order_payloads: list[dict] | None = None,
    publisher: RecordingPublisher | None = None,
) -> tuple[EnableTradingCommandHandler, TradingSessionState, Mock, Mock]:
    account_reader = Mock()
    account_reader.check_connection.return_value = status or _ready_status()

    raw_client = Mock()
    raw_client.futures_position_information.return_value = position_payloads or []
    raw_client.futures_get_open_orders.return_value = open_order_payloads or []
    # `EPIC-028R` — conditional orders live in Binance's Algo Order API.
    raw_client.futures_get_open_algo_orders.return_value = algo_order_payloads or []
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = Mock()
    trading_client_factory = FuturesTradingClientFactory(
        session_factory, credentials_provider, metadata_provider
    )
    session_state = TradingSessionState()
    user_data_stream = Mock()

    return (
        EnableTradingCommandHandler(
            single_venue_scopes(
                venue_context(
                    trading_venue,
                    account_reader=account_reader,
                    client_factory=trading_client_factory,
                    user_data_stream=user_data_stream,
                ),
                session_state,
            ),
            publisher or RecordingPublisher(),
        ),
        session_state,
        user_data_stream,
        account_reader,
    )


def test_enables_when_account_is_flat() -> None:
    handler, session_state, user_data_stream, _account_reader = _handler()

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert result.enabled is True
    assert result.block_reason is None
    assert result.account_was_read is True
    assert session_state.enabled is True
    user_data_stream.start.assert_called_once()


def test_blocked_when_trading_venue_disabled() -> None:
    handler, session_state, user_data_stream, _account_reader = _handler(
        trading_venue=TradingVenue.DISABLED
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.DISABLED))

    assert result.enabled is False
    assert result.block_reason is EnableTradingBlockReason.TRADING_VENUE_DISABLED
    assert result.account_was_read is False  # nothing was asked of the venue
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_enables_when_trading_venue_is_spot_testnet() -> None:
    """`EPIC-027K` — the gate asks `TradingVenue.supports_order_submission`,
    not a literal `is not FUTURES_TESTNET`. `SPOT_TESTNET` now has a real
    order-submission implementation (`SpotTradingClient`), so this gate no
    longer blocks it."""
    handler, session_state, user_data_stream, _account_reader = _handler(
        trading_venue=TradingVenue.SPOT_TESTNET
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.SPOT_TESTNET))

    assert result.enabled is True
    assert result.block_reason is None
    assert session_state.enabled is True
    user_data_stream.start.assert_called_once()


def test_blocked_when_connection_not_reachable() -> None:
    unreachable = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.NETWORK,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )
    handler, session_state, user_data_stream, _account_reader = _handler(
        status=unreachable
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert result.block_reason is EnableTradingBlockReason.CONNECTION_NOT_READY
    assert result.account_was_read is False  # positions were never read
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_blocked_when_hedge_mode() -> None:
    hedge_mode = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.HEDGE,
        margin_type=None,
        open_position_count=0,
    )
    handler, session_state, user_data_stream, _account_reader = _handler(
        status=hedge_mode
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert result.block_reason is EnableTradingBlockReason.CONNECTION_NOT_READY
    assert result.account_was_read is False
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_a_concurrent_emergency_stop_during_reconciliation_is_not_overridden() -> None:
    """`BUG-088` — `EnableTradingCommand` does two network round-trips
    (`check_connection()`, `get_positions()`/`get_open_orders()`) before it
    ever calls `session_state.enable()`. If an Emergency Stop's `disable()`
    lands on another thread while that reconciliation is still in flight,
    a blind `enable()` afterward would silently turn trading back on right
    after the user asked for everything to stop. Simulated deterministically
    here by having the connection check itself trigger the concurrent
    `disable()` — no real threads needed."""
    handler, session_state, user_data_stream, account_reader = _handler()

    def _check_connection_then_concurrent_emergency_stop() -> ExchangeConnectionStatus:
        session_state.disable()  # the "Emergency Stop that ran meanwhile"
        return _ready_status()

    account_reader.check_connection.side_effect = (
        _check_connection_then_concurrent_emergency_stop
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert result.enabled is False
    assert (
        result.block_reason
        is EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE
    )
    assert result.account_was_read is True  # read before the stop landed
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_refuses_and_does_not_enable_when_unexpected_position_exists() -> None:
    """`EPIC-021G` §2.4: an existing position the app has no record of
    refuses the enable — it is never auto-adopted, never auto-closed."""
    handler, session_state, user_data_stream, _account_reader = _handler(
        position_payloads=[_position_payload()]
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert result.enabled is False
    assert result.block_reason is EnableTradingBlockReason.UNEXPECTED_POSITIONS
    assert result.account_was_read is True
    assert len(result.reconciled_positions) == 1
    assert result.reconciled_positions[0].symbol == "BTCUSDT"
    assert session_state.enabled is False
    user_data_stream.start.assert_not_called()


def test_enables_without_any_strategy_armed() -> None:
    """`BUG-112` — `EPIC-022B` originally refused to enable trading with
    nothing armed ("trading enabled" would describe a system that could
    never produce a signal). `EPIC-024B` gave `ExecuteOrderCommand` a
    second, independent caller — a human, via the manual order card — so
    that premise stopped being true: a user who wants *only* manual
    trading now has a real reason to enable trading with no strategy
    armed at all, and used to be forced into arming one just to unlock
    the switch, then getting immediately blocked from manually trading
    that exact symbol by the armed-symbol hard block (`PRO-003` §4.1.2) —
    a genuine deadlock a user hit and reported directly. This is the fix:
    no strategy required, ordinary reconciliation still runs."""
    handler, session_state, user_data_stream, _account_reader = _handler()

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert result.enabled is True
    assert result.block_reason is None
    assert session_state.enabled is True
    user_data_stream.start.assert_called_once()


def _spot_status(holdings: tuple[SpotHolding, ...] = ()) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        holdings=holdings,
        equity=Decimal(1000),
    )


def test_records_a_spot_baseline_from_current_holdings() -> None:
    """`EPIC-027M` AC1 — the exact fact `EmergencyStopCommandHandler` later
    needs: what the account held the moment this app turned trading on."""
    status = _spot_status(
        holdings=(
            SpotHolding(
                asset="BTC",
                free=Decimal("0.5"),
                locked=Decimal(0),
                dust_threshold=Decimal("0.00000001"),
            ),
        )
    )
    handler, session_state, _user_data_stream, _account_reader = _handler(
        trading_venue=TradingVenue.SPOT_TESTNET, status=status
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.SPOT_TESTNET))

    assert result.enabled is True
    assert session_state.spot_baseline_holdings() == {"BTC": Decimal("0.5")}


def test_records_an_empty_spot_baseline_when_holding_nothing() -> None:
    handler, session_state, _user_data_stream, _account_reader = _handler(
        trading_venue=TradingVenue.SPOT_TESTNET, status=_spot_status()
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.SPOT_TESTNET))

    assert result.enabled is True
    assert session_state.spot_baseline_holdings() == {}


def test_does_not_record_a_spot_baseline_on_futures() -> None:
    """The baseline is a Spot-only concept — a Futures enable must not
    leave one behind for a later Spot session to misread."""
    handler, session_state, _user_data_stream, _account_reader = _handler()

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert result.enabled is True
    assert session_state.spot_baseline_holdings() is None


def test_reconciliation_sees_a_conditional_order_in_the_algo_order_api() -> None:
    """`EPIC-028R` — a stop-limit resting in Binance's Algo Order API is part
    of what Enable reconciles, beside the regular open orders."""
    handler, _state, _raw, _factory = _handler(
        algo_order_payloads=[
            {
                "clientAlgoId": "SEW-a91f4c72e0b8",
                "orderType": "STOP",
                "symbol": "BTCUSDT",
                "side": "SELL",
                "quantity": "0.01",
                "algoStatus": "NEW",
                "triggerPrice": "49000",
                "price": "48900",
                "timeInForce": "GTC",
            }
        ]
    )

    result = handler.execute(EnableTradingCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert [o.client_order_id for o in result.reconciled_open_orders] == [
        "SEW-a91f4c72e0b8"
    ]
    assert result.reconciled_open_orders[0].order_type is OrderType.STOP_LIMIT
