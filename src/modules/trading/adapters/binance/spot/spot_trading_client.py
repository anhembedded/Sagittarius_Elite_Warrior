"""`EPIC-027K` — `ITradingClient` implementation: the adapter that actually
sends a signed order request to Binance Spot Testnet.

@details Mirrors `FuturesTradingClient`'s own shape (same four constructor
collaborators, same `OrderSubmissionMode`-gated `create_test_order`/
`create_order` branch, same `BinanceAPIException` -> `OrderRejectedByExchangeError`
translation) — see that adapter's own module docstring for the reasoning
this one shares unchanged.

Two real differences from Futures, both Binance API facts, not a design
choice:
- `get_positions()` always returns `[]`. A Spot account has no leveraged
  positions to report — only balances, already served by
  `ITradingAccountReader`/`SpotHolding` (`EPIC-027H`). Every real caller of
  `ITradingClient.get_positions()` (`get_open_positions`, `enable_trading`,
  `emergency_stop`, the user-data-stream reconciliation) already treats an
  empty list as the legitimate "flat" state, so this is not a fabricated
  answer — it is the true one for this venue.
- `cancel_all_orders()` does not need to read `get_open_orders()` first the
  way `FuturesTradingClient` does: Binance Spot's own `DELETE
  /api/v3/openOrders` returns the list of orders it canceled directly
  (verified against `tests/sanity/fake_exchange/spot_account_state.py`'s own
  `cancel_all()`, itself sourced from Binance's documented response shape
  for this exact endpoint) — Futures' endpoint only ever returns a bare
  acknowledgement, which is why that adapter reads first.
"""

from __future__ import annotations

from typing import NoReturn

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_error_translator import (
    translate_binance_error,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_order_payload_mapper import (
    map_order_to_spot_params,
    map_spot_order_payload_to_order,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)


class SpotTradingClient(ITradingClient):
    """@brief The Spot half of the one instance in this app allowed to sign
    an order request (ADR §2.1) — always Spot Testnet, `TradingVenue` has no
    Spot mainnet member (ADR D8), so this is never ambiguous."""

    def __init__(
        self,
        session_factory: ISpotSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
        submission_mode: OrderSubmissionMode,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider
        self._submission_mode = submission_mode

    def place_order(self, order: Order) -> Order:
        """@raise ValueError No credentials configured, or `order.symbol`
        is not a known Spot symbol.
        @raise InvalidOrderForSubmissionError `order.order_type` is not
        `MARKET`/`LIMIT`, or `order` is not already rounded to the
        symbol's filters (see the mapper's own docstring).
        @raise OrderRejectedByExchangeError The exchange refused the
        request — including a `VALIDATE_ONLY` refusal.
        @return `order` unchanged on acceptance, matching
        `FuturesTradingClient`'s own contract: the authoritative order
        lifecycle is what the Spot User Data Stream (`EPIC-027L`) reports,
        not this call's return value.
        """
        client = self._resolve_client()
        metadata = self._require_metadata(order.symbol)
        params = map_order_to_spot_params(order, metadata)

        try:
            if self._submission_mode is OrderSubmissionMode.VALIDATE_ONLY:
                client.create_test_order(**params)
            else:
                client.create_order(**params)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return order

    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        client = self._resolve_client()
        try:
            payload = client.cancel_order(
                symbol=symbol, origClientOrderId=client_order_id
            )
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return map_spot_order_payload_to_order(payload)

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        client = self._resolve_client()
        try:
            payloads = client.cancel_all_open_orders(symbol=symbol)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return [map_spot_order_payload_to_order(payload) for payload in payloads]

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        client = self._resolve_client()
        request_kwargs = {"symbol": symbol} if symbol else {}
        try:
            payloads = client.get_open_orders(**request_kwargs)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return [map_spot_order_payload_to_order(payload) for payload in payloads]

    def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
        """@brief Always empty — see this module's own docstring for why
        that is the true answer for Spot, not a fabricated one."""
        return []

    def _resolve_client(self) -> ISpotSessionClient:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            raise ValueError(
                "No exchange credentials configured — cannot sign a trading request."
            )
        return self._session_factory.create_trading_client(resolution.credentials)

    def _require_metadata(self, symbol: str) -> SymbolOrderMetadata:
        metadata = self._metadata_provider.get_or_fetch(symbol)
        if metadata is None:
            raise ValueError(f"Unknown Spot symbol: {symbol}")
        return metadata


def _raise_rejection(exc: BinanceAPIException) -> NoReturn:
    reason = translate_binance_error(exc)
    raise OrderRejectedByExchangeError(reason, str(exc)) from exc
