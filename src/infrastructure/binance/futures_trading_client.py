"""`EPIC-021F` — `ITradingClient` implementation: the adapter that actually
sends a signed order request to Binance Futures Testnet.

@details Constructed with a fixed `OrderSubmissionMode` — see that enum's
own docstring for why this is a constructor parameter, not a per-call
flag. `EPIC-021F` only ever wires `VALIDATE_ONLY` (`POST
/fapi/v1/order/test`): the exchange validates signature, permissions, and
payload in full, but never queues the order for matching. Nothing in this
repo is allowed to construct this adapter with `OrderSubmissionMode.LIVE`
until `EPIC-021G` — guarded by
`tests/unit/infrastructure/binance/test_order_submission_mode_live_is_restricted.py`.

Only `BinanceAPIException` (a response the exchange actually sent back,
carrying a code) is translated into a named `OrderRejectedByExchangeError`
here. A network-level failure (`BinanceRequestException`,
`requests.exceptions.RequestException`, or the construction-time ping
`Client(...)` performs itself — same trigger as `BUG-045`) is left to
propagate: `ITradingClient` makes no "never raises" promise the way
`ITradingAccountReader` (`EPIC-021D`) does, and a caller two frames up
already has to decide what "no connection" means for its own UI/CLI —
translating it into an order-rejection reason here would misname a
problem that has nothing to do with the order's content.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NoReturn

from binance.client import Client
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_error_translator import (
    translate_binance_error,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_order_payload_mapper import (
    map_futures_order_payload_to_order,
    map_futures_position_payload_to_live_position,
    map_order_to_futures_params,
)


class FuturesTradingClient(ITradingClient):
    """@brief The one instance in this app allowed to sign an order request
    (ADR §2.1). Always Futures Testnet — `TradingVenue` has no `MAINNET`
    member (ADR §3), so this is never ambiguous.
    """

    def __init__(
        self,
        session_factory: ExchangeSessionFactory,
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
        is not a known futures symbol.
        @raise InvalidOrderForSubmissionError `order` is not already
        rounded to the symbol's filters (see the mapper's own docstring).
        @raise OrderRejectedByExchangeError The exchange refused the
        request — including a `VALIDATE_ONLY` refusal, which is exactly
        `EPIC-021F`'s own runnable milestone's rejected case.
        @return `order` unchanged on acceptance. Binance's synchronous
        response is not parsed into an updated status here: the
        authoritative order lifecycle (`NEW` -> `PARTIALLY_FILLED` -> ...)
        is what `EPIC-021H`'s User Data Stream exists to report, not this
        call's return value.
        """
        client = self._resolve_client()
        metadata = self._require_metadata(order.symbol)
        params = map_order_to_futures_params(order, metadata)

        try:
            if self._submission_mode is OrderSubmissionMode.VALIDATE_ONLY:
                client.futures_create_test_order(**params)
            else:
                client.futures_create_order(**params)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return order

    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        client = self._resolve_client()
        try:
            payload = client.futures_cancel_order(
                symbol=symbol, origClientOrderId=client_order_id
            )
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return map_futures_order_payload_to_order(payload)

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        # `futures_cancel_all_open_orders` only ever returns a bare
        # acknowledgement ({"code": 200, "msg": "..."}), never the list of
        # orders it canceled — so what would have been canceled is read
        # *before* issuing the cancel, and returned as the best available
        # answer to "which orders did this affect".
        orders = self.get_open_orders(symbol)
        client = self._resolve_client()
        try:
            client.futures_cancel_all_open_orders(symbol=symbol)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return orders

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        client = self._resolve_client()
        request_kwargs = {"symbol": symbol} if symbol else {}
        try:
            payloads = client.futures_get_open_orders(**request_kwargs)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return [map_futures_order_payload_to_order(payload) for payload in payloads]

    def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
        client = self._resolve_client()
        request_kwargs = {"symbol": symbol} if symbol else {}
        try:
            payloads = client.futures_position_information(**request_kwargs)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return [
            map_futures_position_payload_to_live_position(payload)
            for payload in payloads
            if Decimal(str(payload.get("positionAmt", "0"))) != 0
        ]

    def _resolve_client(self) -> Client:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            raise ValueError(
                "No exchange credentials configured — cannot sign a trading request."
            )
        # `Client(...)`'s own constructor pings on construction by default
        # (same trigger as `BUG-045`/`EPIC-021D` §4) — letting that raise
        # straight through here is deliberate, see this module's docstring.
        return self._session_factory.create_trading_client(resolution.credentials)

    def _require_metadata(self, symbol: str) -> FuturesSymbolMetadata:
        metadata = self._metadata_provider.get_or_fetch(symbol)
        if metadata is None:
            raise ValueError(f"Unknown futures symbol: {symbol}")
        return metadata


def _raise_rejection(exc: BinanceAPIException) -> NoReturn:
    reason = translate_binance_error(exc)
    raise OrderRejectedByExchangeError(reason, str(exc)) from exc
