"""The builders the `EmergencyStopCommandHandler` tests share (`BOT-146`).

`test_emergency_stop.py` outgrew the 400-line ceiling. Its Spot steps moved to
`test_emergency_stop_spot.py`, and both import the handler and payloads from
here rather than keeping a copy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.handler import (
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
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

CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")


class StaticMetadataProvider(IMarketMetadataProvider):
    def __init__(self, catalog: dict[str, SymbolOrderMetadata]) -> None:
        self._catalog = catalog

    def get_or_fetch(self, symbol: str) -> SymbolOrderMetadata | None:
        return self._catalog.get(symbol)

    def refresh(self) -> None:
        raise NotImplementedError


def static_metadata_provider() -> IMarketMetadataProvider:
    return StaticMetadataProvider(
        {
            "BTCUSDT": SymbolOrderMetadata(
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


def open_order_payload(symbol: str = "BTCUSDT", client_order_id: str = "SEW-1") -> dict:
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


def position_payload(symbol: str = "BTCUSDT", amt: str = "0.002") -> dict:
    # `BUG-114` — real `/fapi/v3/positionRisk` carries no `leverage`/
    # `marginType` field; `notional`/`initialMargin`/`isolatedMargin` are
    # what the mapper actually derives them from now (see
    # `futures_order_payload_mapper.py`). Values here are not meant to
    # reflect `amt` — this file never asserts leverage/margin type.
    return {
        "symbol": symbol,
        "positionAmt": amt,
        "entryPrice": "64000.00",
        "markPrice": "64500.00",
        "unRealizedProfit": "1.00",
        "notional": "128.00",
        "initialMargin": "12.80",
        "isolatedMargin": "0",
        "liquidationPrice": "0",
        "updateTime": 0,
    }


def make_handler(
    *,
    session_state: TradingSessionState | Mock | None = None,
    user_data_stream: Mock | None = None,
    raw_client: Mock | None = None,
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    account_reader: FakeTradingAccountReader | None = None,
    metadata_provider: IMarketMetadataProvider | None = None,
    publisher: RecordingPublisher | None = None,
) -> EmergencyStopCommandHandler:
    session_factory = Mock()
    session_factory.create_trading_client.return_value = without_algo_orders(
        raw_client or Mock()
    )
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        CREDENTIALS, CredentialsSource.FILE
    )
    trading_client_factory = FuturesTradingClientFactory(
        session_factory, credentials_provider, static_metadata_provider()
    )
    context = venue_context(
        trading_venue,
        account_reader=(
            account_reader if account_reader is not None else FakeTradingAccountReader()
        ),
        client_factory=trading_client_factory,
        metadata_provider=metadata_provider or static_metadata_provider(),
        user_data_stream=user_data_stream or Mock(),
    )
    return EmergencyStopCommandHandler(
        single_venue_scopes(
            context,
            session_state if session_state is not None else TradingSessionState(),
        ),
        publisher or RecordingPublisher(),
    )


def without_algo_orders(raw_client: Mock) -> Mock:
    """`EPIC-028R` — the account holds no conditional order (Binance's Algo
    Order API) unless a test arranges one, so a test about regular orders
    keeps reading only what it arranged."""
    algo = raw_client.futures_get_open_algo_orders
    if algo.side_effect is None and not isinstance(algo.return_value, list):
        algo.return_value = []
    return raw_client


def quiet_raw_client() -> Mock:
    """No open orders, no positions — the common case for tests that only
    care about one step."""
    raw_client = Mock()
    raw_client.futures_get_open_orders.return_value = []
    raw_client.futures_position_information.return_value = []
    return raw_client


def spot_status(holdings: tuple[SpotHolding, ...] = ()) -> ExchangeConnectionStatus:
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
