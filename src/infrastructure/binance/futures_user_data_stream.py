"""`EPIC-021H` — `IUserDataStream` implementation: the exchange's own
account of what happened to an order, over Binance Futures' User Data
Stream (`ORDER_TRADE_UPDATE`/`ACCOUNT_UPDATE`).

@details Same `ITaskManager.spawn`/`CancellationToken` shape as
`BinanceWebsocketService` (`EPIC-021A`) — cooperative exit, client closed
in `finally`. A separate file, not folded into that service: different
credentials (signed), different failure consequences (losing this stream
leaves the app blind about its own money, not merely a frozen chart), and
`architecture-rule.md` §5.5's own test — changing kline handling never
has to touch this — answers "no".

@par `listenKey` lifecycle: delegated, not reimplemented
`EPIC-021H` §2.2 asks for periodic renewal and recreation-on-reconnect,
with an `INFO` log when that happens. `python-binance`'s own
`BinanceSocketManager.futures_user_socket()` already does exactly this
(`KeepAliveWebsocket`, verified by reading its source): it re-requests a
listen key on a timer, and Binance's `POST listenKey` endpoint is itself a
"create-or-extend" call — the same key comes back if it is still valid,
a genuinely new one if it had expired, and the library reconnects with
the fresh key when that happens. Hand-rolling this against the three raw
`AsyncClient` methods (`futures_stream_get_listen_key`/`_keepalive`/
`_close`) would be a second, unreviewed implementation of logic the
library already gets right — so this adapter uses the public
`futures_user_socket()` entry point rather than the private
`_get_futures_socket()` one, and does not carry its own listen-key timer.
This is a deliberate scope narrowing from the task's literal wording; see
this epic's own implementation notes (§6) for the full reasoning.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from binance import AsyncClient, BinanceSocketManager
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.application.services.position_state_reconciler import (
    reconcile_position_state,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.domain.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.user_data_event_parser import (
    ACCOUNT_UPDATE,
    ORDER_TRADE_UPDATE,
    account_update_changed_symbols,
    account_update_equity_sample,
    fill_details,
    is_fill_execution,
    parse_order_trade_update,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.UserDataStream")

_RECONNECT_DELAY_SECONDS = 5


class FuturesUserDataStream(IUserDataStream):
    """@details Builds its own `FuturesTradingClient` (`VALIDATE_ONLY` —
    irrelevant for the read-only `get_positions()` call this uses it for)
    from raw collaborators, the same reasoning `ExecuteOrderCommandHandler`/
    `EnableTradingCommandHandler` already use (`EPIC-021G`): depending on
    the `ITradingClient` singleton directly would only be safely
    constructible when `TradingVenue != DISABLED`, and this class must stay
    constructible (and therefore safely injectable into
    `EnableTradingCommandHandler`) regardless.
    """

    def __init__(
        self,
        event_bus: IEventBus,
        task_manager: ITaskManager,
        session_factory: ExchangeSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
        session_state: TradingSessionState,
        equity_recorder: EquityCurveRecorder,
    ) -> None:
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider
        self._session_state = session_state
        self._equity_recorder = equity_recorder
        self._trading_client: ITradingClient | None = None
        self._task_handle: ITaskHandle | None = None
        self._token: CancellationToken | None = None

    def start(self) -> bool:
        if self._task_handle is not None:
            logger.warning("User data stream is already running. Stop it first.")
            return False

        self._token = CancellationToken()
        logger.info("Starting Binance Futures user data stream...")
        self._task_handle = self._task_manager.spawn(
            self._run_stream(self._token),
            name="FuturesUserDataStream",
            token=self._token,
            critical=True,
        )
        return True

    def stop(self) -> bool:
        if self._task_handle is None:
            logger.debug("Stop requested but user data stream is not running.")
            return False

        logger.info("Stopping Binance Futures user data stream...")
        if self._token is not None:
            self._token.cancel()
        self._task_handle.cancel()
        self._task_handle = None
        self._token = None
        return True

    async def _run_stream(self, token: CancellationToken) -> None:
        # Resolved here, not cached at construction time: `EnableTradingCommand`
        # already proved credentials resolve (via `ITradingAccountReader.
        # check_connection()`) before this stream is ever started, but a
        # `FuturesUserDataStream` must still be safely *constructible* with no
        # credentials configured at all (same reasoning as `FuturesTradingClient.
        # _resolve_client()`, EPIC-021F).
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            logger.error(
                "No exchange credentials configured — cannot open the user data stream."
            )
            return

        self._trading_client = FuturesTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            OrderSubmissionMode.VALIDATE_ONLY,
        )

        is_closing = False
        client: AsyncClient | None = None
        try:
            client = await AsyncClient.create(
                api_key=resolution.credentials.api_key,
                api_secret=resolution.credentials.api_secret,
                testnet=True,
            )
            bsm = BinanceSocketManager(client)

            while not token.is_cancelled():
                try:
                    socket = bsm.futures_user_socket()
                    async with socket as stream:
                        while not token.is_cancelled():
                            res = await stream.recv()
                            if res:
                                self._handle_message(res)
                except asyncio.CancelledError:
                    logger.info("User data stream task was cancelled.")
                    break
                except OSError as exc:
                    if not token.is_cancelled():
                        logger.error(
                            "User data stream connection error: %s. "
                            "Reconnecting in %ss...",
                            exc,
                            _RECONNECT_DELAY_SECONDS,
                        )
                        await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
        except GeneratorExit:
            is_closing = True
            raise
        finally:
            if client is not None and not is_closing:
                try:
                    await client.close_connection()
                    logger.info("User data stream AsyncClient connection closed.")
                except Exception as exc:  # noqa: BLE001 - boundary: log and continue teardown
                    logger.warning("Error closing user data stream client: %s", exc)

    def _handle_message(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("e")
        if event_type == ORDER_TRADE_UPDATE:
            self._handle_order_trade_update(payload)
        elif event_type == ACCOUNT_UPDATE:
            self._handle_account_update(payload)

    def _handle_order_trade_update(self, payload: dict[str, Any]) -> None:
        try:
            order = parse_order_trade_update(payload)
        except (KeyError, ValueError) as exc:
            logger.error("Could not parse ORDER_TRADE_UPDATE: %s | %s", exc, payload)
            return

        logger.info(
            "ORDER_TRADE_UPDATE  %s  %s  qty %s",
            order.client_order_id,
            order.status.name,
            order.quantity,
        )

        if is_fill_execution(payload):
            fill_price, fill_quantity = fill_details(payload)
            self._event_bus.emit(
                OrderFilledEvent(
                    order=order, fill_price=fill_price, fill_quantity=fill_quantity
                )
            )

    def _handle_account_update(self, payload: dict[str, Any]) -> None:
        if self._trading_client is None:
            # Only reachable if a caller invokes `_handle_message` directly
            # before `_run_stream` has ever set it up — the real socket
            # loop never calls this until construction above has run.
            logger.error("ACCOUNT_UPDATE received before the stream was ready.")
            return

        # `EPIC-021M` §2.1 — sampled from the same stream message, no extra
        # request. `None` when this update carries no balance entry for the
        # quote asset (e.g. a position-only update) — nothing to record.
        equity_sample = account_update_equity_sample(payload)
        if equity_sample is not None:
            self._equity_recorder.record(equity_sample)
            self._event_bus.emit(EquitySampledEvent(sample=equity_sample))
            logger.info(
                "ACCOUNT_UPDATE  equity  wallet %s  uPnL %s  total %s",
                equity_sample.wallet_balance,
                equity_sample.unrealized_pnl,
                equity_sample.total,
            )

        for symbol in account_update_changed_symbols(payload):
            positions = self._trading_client.get_positions(symbol)
            reconcile_position_state(
                self._session_state, symbol, has_position=bool(positions)
            )
            if positions:
                self._event_bus.emit(PositionChangedEvent(position=positions[0]))
                logger.info(
                    "ACCOUNT_UPDATE  %s  pos %s  entry %s  uPnL %s",
                    symbol,
                    positions[0].position_amt,
                    positions[0].entry_price,
                    positions[0].unrealized_pnl,
                )
            else:
                # `BUG-086` — a closed position is a real change too, not
                # merely absence of one; `PositionChangedEvent` cannot
                # carry it (no `LivePosition` to construct — its own
                # docstring forbids `position_amt == 0`), so this is a
                # dedicated event.
                self._event_bus.emit(PositionClosedEvent(symbol=symbol))
                logger.info("ACCOUNT_UPDATE  %s  position closed", symbol)
