"""`EPIC-027L` — `IUserDataStream` implementation for Binance Spot: the
exchange's own account of what happened to an order, over Spot's User Data
Stream (`executionReport`/`outboundAccountPosition`/`balanceUpdate`).

@details Mirrors `FuturesUserDataStream`'s own connection/reconnect
mechanism (`ITaskManager.spawn`/`CancellationToken`, `BUG-094`'s generation
fencing, `BUG-096`'s `{"e": "error"}` sentinel handling, `bsm.<x>_socket()`
re-entry to revive the library's own reconnect budget) verbatim — only the
socket method (`bsm.user_socket()`, verified by reading `python-binance`'s
own source) and the payload parser (`spot_user_data_event_parser.py`)
differ.

@par A smaller dependency set than Futures, on purpose
Spot has no position-reconciliation concept (`TradingSessionState`/
`ITradingClientFactory` exist to answer "is this account now flat", which
only makes sense where leverage/positions exist — ADR D8), so this class
takes neither. Equity comes from `ITradingAccountReader.check_connection()`
— the same authoritative Spot equity/holdings computation `EPIC-027H`
already built — re-fetched on every `outboundAccountPosition`, never
computed from the stream's own balance deltas: the exchange's REST answer is
the source of truth, matching Futures' own "re-fetch, never trust a
streamed delta alone" principle (`FuturesUserDataStream._handle_account_
update`'s own `get_positions()` re-fetch), just applied to the Spot-
appropriate source.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from binance import AsyncClient, BinanceSocketManager
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.managed_user_data_stream import (
    ManagedUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_event_parser import (
    BALANCE_UPDATE,
    EXECUTION_REPORT,
    OUTBOUND_ACCOUNT_POSITION,
    fill_details,
    fill_fee,
    fill_trade_id,
    is_fill_execution,
    parse_execution_report,
    stream_event_captured_at,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_stream_supervisor import (
    DEFAULT_RECONNECT_POLICY,
    ReconnectPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    ended_without_filling,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.UserDataStream")

#: `BUG-096` — the same `python-binance`-internal reconnect sentinel
#: `FuturesUserDataStream` already documents (not a Binance wire-protocol
#: event); duplicated here rather than imported since it describes this
#: adapter's own relationship with the library, not the exchange's protocol.
_LIBRARY_ERROR_EVENT = "error"


class SpotUserDataStream(ManagedUserDataStream):
    """@details Resolves `ITradingAccountReader` for its Spot equity
    re-fetch — not `ITradingClientFactory`: that port exists to build order-
    submitting clients (`EPIC-027F`), and this stream never submits an
    order, only reads. `credentials_provider` stays its own constructor
    parameter, same reasoning as `FuturesUserDataStream`: `_run_stream()`
    opens the raw signed websocket directly, which needs credentials on
    their own.
    """

    def __init__(
        self,
        events: VenueEventEmitter,
        task_manager: ITaskManager,
        credentials_provider: IExchangeCredentialsProvider,
        account_reader: ITradingAccountReader,
        equity_recorder: EquityCurveRecorder,
        reconnect_policy: ReconnectPolicy = DEFAULT_RECONNECT_POLICY,
    ) -> None:
        super().__init__(events, task_manager, "SpotUserDataStream", reconnect_policy)
        #: `EPIC-028C` — this venue's emitter: every event carries the venue.
        self._events = events
        self._credentials_provider = credentials_provider
        self._account_reader = account_reader
        self._equity_recorder = equity_recorder

    async def _run_stream(self, token: CancellationToken, generation: int) -> None:
        # Resolved here, not cached at construction time: this class must
        # stay safely constructible with no credentials configured at all
        # (same reasoning as `FuturesUserDataStream._run_stream`).
        resolved = self._credentials_provider.resolve()
        credentials = resolved.credentials
        if credentials is None:
            logger.error(resolved.unusable_because("Spot", "open the user data stream"))
            return

        def is_current() -> bool:
            return not token.is_cancelled() and generation == self._generation

        await self._supervisor.run(
            lambda connected: self._run_session(
                credentials, connected, is_current, generation
            ),
            is_current,
        )

    async def _run_session(
        self,
        credentials: ExchangeCredentials,
        connected: Callable[[], None],
        is_current: Callable[[], bool],
        generation: int,
    ) -> None:
        """One connection: a fresh client and socket, read until the stream is
        no longer current. Any failure propagates to the supervisor, which
        retries with backoff (`EPIC-035B`); a fresh client each time also
        covers an API error while creating it (clock skew, a banned IP)."""
        is_closing = False
        client: AsyncClient | None = None
        try:
            client = await AsyncClient.create(
                api_key=credentials.api_key,
                api_secret=credentials.api_secret,
                testnet=self._events.venue.is_testnet,
            )
            bsm = BinanceSocketManager(client)
            async with bsm.user_socket() as stream:
                connected()
                while is_current():
                    res = await stream.recv()
                    # Re-checked after `await`, not just in the loop
                    # condition above: `stop()`/a new `start()` can bump
                    # `self._generation` while this coroutine was suspended
                    # waiting on `stream.recv()`.
                    if res and generation == self._generation:
                        await self._handle_message(res)
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

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("e")
        if event_type == EXECUTION_REPORT:
            self._handle_execution_report(payload)
        elif event_type in (OUTBOUND_ACCOUNT_POSITION, BALANCE_UPDATE):
            await self._refresh_equity(payload)
        elif event_type == _LIBRARY_ERROR_EVENT:
            logger.warning(
                "User data stream reported a connection issue: %s (%s)",
                payload.get("m"),
                payload.get("type"),
            )

    def _handle_execution_report(self, payload: dict[str, Any]) -> None:
        try:
            order = parse_execution_report(payload)
        except (KeyError, ValueError) as exc:
            logger.error("Could not parse executionReport: %s | %s", exc, payload)
            return

        # `BUG-095` — `DEBUG`, not `INFO`: fires per order-status transition,
        # the same hot-path class `FuturesUserDataStream` already documents.
        logger.debug(
            "executionReport  %s  %s  qty %s",
            order.client_order_id,
            order.status.name,
            order.quantity,
        )

        if is_fill_execution(payload):
            fill_price, fill_quantity = fill_details(payload)
            fee = fill_fee(payload)
            self._events.order_filled(
                order, (fill_price, fill_quantity), fee, fill_trade_id(payload)
            )
        elif ended_without_filling(order.status):
            # `EPIC-028I` — cancelled, rejected or expired.
            self._events.order_ended(order)

    async def _refresh_equity(self, payload: dict[str, Any]) -> None:
        """@brief Handles both `OUTBOUND_ACCOUNT_POSITION` (every fill) and
        `BALANCE_UPDATE` (a deposit/withdrawal/dust conversion — the one
        balance change a fill never produces) identically: no
        position-changed/closed concept exists for Spot (ADR D8: holdings,
        not leveraged positions), so either event only ever triggers an
        authoritative equity re-fetch, never a value derived from the
        stream's own balance deltas (this module's own docstring)."""
        # `BOT-145` — off the event loop: `check_connection()` is several
        # blocking, `requests`-backed REST calls, and this handler runs on
        # the same loop driving `stream.recv()` (`_run_stream`). `BUG-094` —
        # re-fenced after that await: `stop()`/`start()` can bump
        # `self._generation` during the round trip, and a superseded
        # stream must not record or publish into the new session.
        generation = self._generation
        status = await asyncio.to_thread(self._account_reader.check_connection)
        if generation != self._generation:
            return
        if status.equity is None:
            logger.warning(
                "%s received but equity could not be re-fetched — skipping "
                "this equity sample.",
                payload.get("e"),
            )
            return

        equity_sample = EquitySample(
            captured_at=stream_event_captured_at(payload),
            wallet_balance=status.equity,
            unrealized_pnl=Decimal(0),
        )
        self._equity_recorder.record(equity_sample)
        self._events.equity_sampled(equity_sample)
        # `BUG-095` — `DEBUG`: fires on every balance-affecting event, which
        # on an active session is every fill.
        logger.debug("%s  equity  total %s", payload.get("e"), equity_sample.total)
