"""`EPIC-021F` — `ITradingClient` implementation: the adapter that actually
sends a signed order request to Binance Futures Testnet.

@details Constructed with a fixed `OrderSubmissionMode` — see that enum's
own docstring for why this is a constructor parameter, not a per-call
flag. `EPIC-021F` only ever wires `VALIDATE_ONLY` (`POST
/fapi/v1/order/test`): the exchange validates signature, permissions, and
payload in full, but never queues the order for matching. Nothing in this
repo is allowed to construct this adapter with `OrderSubmissionMode.LIVE`
until `EPIC-021G` — guarded by
`tests/unit/architecture/test_order_submission_mode_live_is_restricted.py`.

Only `BinanceAPIException` (a response the exchange actually sent back,
carrying a code) is translated into a named `OrderRejectedByExchangeError`
here. A network-level failure (`BinanceRequestException`,
`requests.exceptions.RequestException`; `Client(...)` no longer pings on
construction, `EPIC-028P`) is left to
propagate: `ITradingClient` makes no "never raises" promise the way
`ITradingAccountReader` (`EPIC-021D`) does, and a caller two frames up
already has to decide what "no connection" means for its own UI/CLI —
translating it into an order-rejection reason here would misname a
problem that has nothing to do with the order's content.

`EPIC-028R` — a stop-limit goes through Binance's Algo Order API
(`futures_algo_order_mapper.py`) with the app's client order id as its
`clientAlgoId`, and every read and cancel covers algo orders too:
`get_open_orders` lists both kinds, `cancel_order` falls back to the algo
cancel when the regular one answers "unknown order", and `cancel_all_orders`
clears both lists, so Emergency Stop cancels a conditional order placed
anywhere, Binance's own UI included.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NoReturn

from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_error_translator import (
    translate_binance_error,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    describe_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_algo_order_mapper import (
    is_algo_routed,
    map_futures_algo_payload_to_order,
    map_order_to_futures_algo_params,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_payload_mapper import (
    map_futures_order_payload_to_order,
    map_futures_position_payload_to_live_position,
    map_order_to_futures_params,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)

#: Binance's "Unknown order sent." — the regular cancel's answer for an id
#: it does not hold, which is what an algo order's id is to it.
_UNKNOWN_ORDER_CODE = -2011


class FuturesTradingClient(ITradingClient):
    """@brief The one instance in this app allowed to sign an order request
    (ADR §2.1). Always Futures Testnet — `TradingVenue` has no `MAINNET`
    member (ADR §3), so this is never ambiguous.
    """

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
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
        if is_algo_routed(order.order_type):
            self._place_algo_order(client, order, metadata)
            return order
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
        """@details A regular order keeps its one request. An id the regular
        cancel does not know (`-2011`) is tried as an algo order's
        `clientAlgoId`; a second "unknown" is the regular cancel's refusal."""
        client = self._resolve_client()
        try:
            payload = client.futures_cancel_order(
                symbol=symbol, origClientOrderId=client_order_id
            )
        except BinanceAPIException as exc:
            if exc.code != _UNKNOWN_ORDER_CODE:
                _raise_rejection(exc)
            return self._cancel_algo_order(client, symbol, client_order_id, exc)
        return map_futures_order_payload_to_order(payload)

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        # Both cancel-all endpoints answer a bare acknowledgement
        # ({"code": 200, "msg": "..."}), never the orders they cancelled, so
        # what they would cancel is read first and returned as the best
        # available answer. The algo cancel runs even when the read found
        # none, so an algo order placed in between is cancelled too.
        orders = self.get_open_orders(symbol)
        client = self._resolve_client()
        try:
            client.futures_cancel_all_open_orders(symbol=symbol)
            client.futures_cancel_all_algo_open_orders(symbol=symbol)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return orders

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """@return Regular and algo open orders together, so reconciliation
        and Emergency Stop see a conditional order wherever it was placed."""
        client = self._resolve_client()
        request_kwargs = {"symbol": symbol} if symbol else {}
        try:
            payloads = client.futures_get_open_orders(**request_kwargs)
            algo_payloads = client.futures_get_open_algo_orders(**request_kwargs)
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return [map_futures_order_payload_to_order(p) for p in payloads] + [
            map_futures_algo_payload_to_order(p) for p in algo_payloads
        ]

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

    def _place_algo_order(
        self,
        client: ITradingSessionClient,
        order: Order,
        metadata: SymbolOrderMetadata,
    ) -> None:
        """@raise InvalidOrderForSubmissionError In `VALIDATE_ONLY` mode: the
        Algo Order API has no test endpoint, and `order/test` would validate a
        different request than the one a live call sends."""
        params = map_order_to_futures_algo_params(order, metadata)
        if self._submission_mode is OrderSubmissionMode.VALIDATE_ONLY:
            raise InvalidOrderForSubmissionError(
                f"{order.order_type.name} cannot be validated without being placed: "
                "Binance's Algo Order API has no test endpoint."
            )
        try:
            client.futures_create_algo_order(**params)
        except BinanceAPIException as exc:
            _raise_rejection(exc)

    @staticmethod
    def _cancel_algo_order(
        client: ITradingSessionClient,
        symbol: str,
        client_order_id: str,
        regular_refusal: BinanceAPIException,
    ) -> Order:
        """Cancels the algo order `client_order_id` names and reads it back:
        the algo cancel answers only an acknowledgement."""
        try:
            client.futures_cancel_algo_order(
                symbol=symbol, clientAlgoId=client_order_id
            )
        except BinanceAPIException:
            # Neither kind holds this id: the regular refusal is the answer.
            _raise_rejection(regular_refusal)
        try:
            payload = client.futures_get_algo_order(
                symbol=symbol, clientAlgoId=client_order_id
            )
        except BinanceAPIException as exc:
            _raise_rejection(exc)
        return map_futures_algo_payload_to_order(payload)

    def _resolve_client(self) -> ITradingSessionClient:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            raise ValueError(
                "No exchange credentials configured — cannot sign a trading request."
            )
        # `Client(...)`'s own constructor pings on construction by default
        # (same trigger as `BUG-045`/`EPIC-021D` §4) — letting that raise
        # straight through here is deliberate, see this module's docstring.
        return self._session_factory.create_trading_client(resolution.credentials)

    def _require_metadata(self, symbol: str) -> SymbolOrderMetadata:
        metadata = self._metadata_provider.get_or_fetch(symbol)
        if metadata is None:
            raise ValueError(f"Unknown futures symbol: {symbol}")
        return metadata


def _raise_rejection(exc: BinanceAPIException) -> NoReturn:
    reason = translate_binance_error(exc)
    raise OrderRejectedByExchangeError(reason, describe_failure(exc)) from exc
