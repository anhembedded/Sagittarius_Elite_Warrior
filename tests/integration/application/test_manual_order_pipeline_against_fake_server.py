"""`EPIC-024B` — the manual trading form's second-caller proof, at the same
depth `test_live_trading_pipeline_against_fake_server.py` already holds the
strategy path to: not "the presenter asked the dispatcher for the right
command" (the unit tests in `test_dashboard_presenter.py` already prove
that), but what actually reaches the exchange once `ExecuteOrderCommand`
crosses `PreviewOrderQueryHandler`'s rounding, `map_order_to_futures_params`,
and `python-binance`'s own form encoding — the exact layers a caller-level
mock can't see past.

@par What this proves, and what it deliberately does not
`GetOpenPositionsQueryHandler` reads the fake server's fixed, always-flat
`/fapi/v3/positionRisk` (`futures_routes.py`'s own docstring: no matching
engine, no position tracking) — so this covers the "flat account, Long
click opens a real BUY" half of `manual_order_intent_for()`'s table. The
"closing an existing position" half (`reduce_only=True`) is already covered
at the unit level (`test_manual_order_intent.py`'s 7 cases,
`test_dashboard_presenter.py::test_run_manual_order_dispatches_execute_order_with_the_mapped_intent`)
— extending the fake server to seed a fixture position for this file too
was judged not worth the added shared-fixture surface for what the mapping
function's own dedicated tests already lock down byte-for-byte.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
    GetOpenPositionsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server

_SYMBOL = "BTCUSDT"
_PRICE = Decimal(64000)

#: `max_notional_per_order` well above 0.01 BTC @ `_PRICE` (640 USDT) —
#: this task's own limits are not what these tests exist to check
#: (`TradingLimitPolicy` already has its own dedicated coverage).
_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(1000),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


class _StubAccountReader(ITradingAccountReader):
    def check_connection(self) -> ExchangeConnectionStatus:
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


class _FakeCredentialsProvider:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this test")


def _orders_the_exchange_received(futures_url: str) -> list[dict[str, Any]]:
    """Same technique `test_live_trading_pipeline_against_fake_server.py`
    uses: read the fixture's own order book over plain HTTP, not through
    this app's adapters."""
    with urllib.request.urlopen(  # noqa: S310 — fixed localhost fixture URL
        f"{futures_url}/v1/openOrders?symbol={_SYMBOL}"
    ) as response:
        payload: list[dict[str, Any]] = json.loads(response.read().decode())
    return payload


def _submit_manual_order(direction: ManualOrderDirection) -> None:
    """The manual order card's own logic (`DashboardPresenter.
    _run_manual_order`), rebuilt here against real collaborators instead of
    a mocked dispatcher — read the real (fake) position, map the click,
    dispatch the real handler."""
    session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
    metadata_provider = FuturesMetadataProvider(
        session_factory, InMemoryFuturesSymbolMetadataCache()
    )
    account_reader = _StubAccountReader()
    credentials_provider = _FakeCredentialsProvider()
    session_state = TradingSessionState()
    session_state.enable(set())

    positions_handler = GetOpenPositionsQueryHandler(
        session_factory, credentials_provider, metadata_provider
    )
    current_position = next(
        (
            p
            for p in positions_handler.execute(GetOpenPositionsQuery())
            if p.symbol == _SYMBOL
        ),
        None,
    )
    intent = manual_order_intent_for(direction, current_position)

    handler = ExecuteOrderCommandHandler(
        TradingVenue.FUTURES_TESTNET,
        session_state,
        account_reader,
        PreviewOrderQueryHandler(metadata_provider),
        TradingLimitPolicy(_LIMITS),
        session_factory,
        credentials_provider,
        metadata_provider,
    )
    result = handler.execute(
        ExecuteOrderCommand(
            order_request=PreviewOrderQuery(
                symbol=_SYMBOL,
                side=intent.side,
                order_type=OrderType.MARKET,
                quantity=Decimal("0.01"),
                reference_price=_PRICE,
                reduce_only=intent.reduce_only,
            ),
            live=True,
        )
    )
    assert result.blocked is False, result.blocked_by


def test_a_flat_accounts_long_click_opens_a_real_buy_on_the_wire() -> None:
    """`PRO-003`/`EPIC-024B`: this task's own proof step — a human's Long
    click, mapped by `manual_order_intent_for()` and dispatched through the
    exact same `ExecuteOrderCommand`/`ExecuteOrderCommandHandler` the
    strategy path uses, must put a real order on the wire."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        _submit_manual_order(ManualOrderDirection.LONG)

        (received,) = _orders_the_exchange_received(urls.futures)
        assert received["symbol"] == _SYMBOL
        assert received["side"] == "BUY"
        assert received["reduceOnly"] is False
        assert received["positionSide"] == "BOTH"
        assert received["type"] == "MARKET"


def test_a_flat_accounts_short_click_opens_a_real_sell_not_a_close() -> None:
    """The other half of the pair — same `side=SELL` a SELL-to-close would
    use, `reduceOnly=False` distinguishes "open SHORT" from it, exactly the
    ambiguity `manual_order_intent_for.py`'s own docstring names."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        _submit_manual_order(ManualOrderDirection.SHORT)

        (received,) = _orders_the_exchange_received(urls.futures)
        assert received["side"] == "SELL"
        assert received["reduceOnly"] is False
        assert received["positionSide"] == "BOTH"
