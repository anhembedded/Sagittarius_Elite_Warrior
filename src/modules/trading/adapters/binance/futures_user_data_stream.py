"""`EPIC-021H` — `IUserDataStream` implementation: the exchange's own
account of what happened to an order, over Binance Futures' User Data
Stream (`ORDER_TRADE_UPDATE`/`ACCOUNT_UPDATE`, and `ALGO_UPDATE` since
`EPIC-028R`).

@details Same `ITaskManager.spawn`/`CancellationToken` shape as
`BinanceWebsocketService` (`EPIC-021A`) — cooperative exit, client closed
in `finally`. A separate file, not folded into that service: different
credentials (signed), different failure consequences (losing this stream
leaves the app blind about its own money, not merely a frozen chart), and
`architecture-rule.md` §5.5's own test — changing kline handling never
has to touch this — answers "no".

@par `listenKey` lifecycle: delegated, not reimplemented
`EPIC-021H` §2.2 asks for periodic renewal and recreation-on-reconnect.
`python-binance`'s own `BinanceSocketManager.futures_user_socket()`
(`KeepAliveWebsocket`, verified by reading its source) does the actual
renewal/reconnect work: it re-requests a listen key on a timer, and
Binance's `POST listenKey` endpoint is itself a "create-or-extend" call —
the same key comes back if it is still valid, a genuinely new one if it
had expired, and the library reconnects with the fresh key when that
happens. Hand-rolling this against the three raw `AsyncClient` methods
(`futures_stream_get_listen_key`/`_keepalive`/`_close`) would be a second,
unreviewed implementation of logic the library already gets right — so
this adapter uses the public `futures_user_socket()` entry point rather
than the private `_get_futures_socket()` one, and does not carry its own
listen-key timer. This is a deliberate scope narrowing from the task's
literal wording; see this epic's own implementation notes (§6) for the
full reasoning.

`BUG-096` correction: the library's own renewal/reconnect logging is
`DEBUG`, under `binance.ws.*` loggers this app's `"App"`-only handler
setup (`logging-rule.md` §1) never sees — it does **not** surface at
`INFO` the way the paragraph above once claimed. What this app *can* see:
the library pushes a `{"e": "error", "type": ..., "m": ...}` sentinel onto
the same queue `stream.recv()` reads from whenever a connection blip
happens (`ConnectionClosedError`, `gaierror`, a timeout, ...) —
`_handle_message` now logs that, which is the only reconnect signal this
adapter can produce without reimplementing the library's internals.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any

from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import ReadLoopClosed
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.algo_update_parser import (
    ALGO_UPDATE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_updates import (
    FuturesOrderUpdates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_data_event_parser import (
    ACCOUNT_UPDATE,
    ORDER_TRADE_UPDATE,
    account_update_captured_at,
    account_update_changed_symbols,
    account_update_position_pnls,
    account_update_wallet_balance,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_state_reconciler import (
    reconcile_position_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.UserDataStream")

_RECONNECT_DELAY_SECONDS = 5

#: `BUG-096` — not a Binance wire-protocol event (unlike `ORDER_TRADE_UPDATE`/
#: `ACCOUNT_UPDATE` in `user_data_event_parser.py`, which owns those): this
#: is `python-binance`'s own internal sentinel, pushed onto the same queue
#: `stream.recv()` reads from whenever its `ReconnectingWebsocket._read_loop`
#: hits a connection error (`ConnectionClosedError`, `gaierror`, a timeout,
#: the reconnect budget running out, ...) — verified by reading
#: `_propagate_error()`'s call sites in the library's own source. Defined
#: here, not in the parser module, since it describes this adapter's
#: relationship with the library, not the exchange's own protocol.
_LIBRARY_ERROR_EVENT = "error"


class FuturesUserDataStream(IUserDataStream):
    """@details Resolves its `ITradingClient` from `ITradingClientFactory`
    (`VALIDATE_ONLY` — irrelevant for the read-only `get_positions()` call
    this uses it for), the same reasoning `ExecuteOrderCommandHandler`/
    `EnsureSessionReadyCommandHandler` already use (`EPIC-021G`): depending on
    the `ITradingClient` singleton directly would only be safely
    constructible when `TradingVenue != DISABLED`, and this class must stay
    constructible (and therefore safely injectable into
    `EnsureSessionReadyCommandHandler`) regardless — `ITradingClientFactory` is
    bound unconditionally (`EPIC-027F`).

    `credentials_provider` stays its own constructor parameter, separate
    from the factory: `_run_stream()` opens the raw signed websocket
    (`AsyncClient.create(api_key=..., api_secret=...)`) directly, which
    needs credentials on their own, not the `ITradingClient` the factory
    builds around them.
    """

    def __init__(
        self,
        events: VenueEventEmitter,
        task_manager: ITaskManager,
        credentials_provider: IExchangeCredentialsProvider,
        trading_client_factory: ITradingClientFactory,
        session_state: TradingSessionState,
        equity_recorder: EquityCurveRecorder,
    ) -> None:
        #: `EPIC-028C` — this venue's emitter: every event carries the venue.
        self._events = events
        self._task_manager = task_manager
        self._credentials_provider = credentials_provider
        self._trading_client_factory = trading_client_factory
        self._session_state = session_state
        self._equity_recorder = equity_recorder
        self._trading_client: ITradingClient | None = None
        self._task_handle: ITaskHandle | None = None
        self._token: CancellationToken | None = None
        #: `BUG-094` — bumped on every `start()`/`stop()`. `ITaskHandle.
        #: cancel()` only *signals* cooperative cancellation
        #: (`CancellationToken`) — it does not wait for `_run_stream()`'s
        #: own teardown to actually finish, so an immediate `start()`
        #: right after `stop()` (an Emergency Stop followed by
        #: `EnsureSessionReadyCommand`, or `EmergencyStopCommandHandler`'s own
        #: step 1 followed by a stray re-enable) can have two `_run_stream()`
        #: coroutines alive at once. Each closure of `_run_stream()`
        #: captures the generation it was spawned with and refuses to
        #: touch shared state (`self._trading_client`, `_handle_message`)
        #: once it no longer matches `self._generation` — the actual
        #: websocket connection may still take a moment to close in that
        #: coroutine's own `finally`, but it stops mutating anything this
        #: class exposes the instant it is superseded.
        self._generation = 0
        #: `BUG-092` — running per-symbol unrealized PnL, folded in from
        #: every `ACCOUNT_UPDATE`'s own `"a"."P"` (which only ever reports
        #: the positions that changed in *that* event, never a full
        #: snapshot — `account_update_position_pnls`'s own docstring).
        #: Summing this running total, not just the current event's
        #: entries, is what makes a multi-position account's equity sample
        #: correct instead of silently missing whichever symbols didn't
        #: change this time. Reset in `start()` — `EnsureSessionReadyCommand`
        #: only ever starts this stream once reconciliation has confirmed
        #: the account is flat, so an empty dict is always the correct
        #: starting point, never a stale carryover from a previous session.
        self._unrealized_pnl_by_symbol: dict[str, Decimal] = {}
        #: `ORDER_TRADE_UPDATE` and, since `EPIC-028R`, `ALGO_UPDATE`.
        self._order_updates = FuturesOrderUpdates(events)

    def start(self) -> bool:
        if self._task_handle is not None:
            logger.warning("User data stream is already running. Stop it first.")
            return False

        self._token = CancellationToken()
        self._unrealized_pnl_by_symbol = {}
        self._generation += 1
        logger.info("Starting Binance Futures user data stream...")
        self._task_handle = self._task_manager.spawn(
            self._run_stream(self._token, self._generation),
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
        # `BUG-094` — bumped here too, not just in `start()`: fences a
        # still-tearing-down `_run_stream()` the instant `stop()` is
        # called, before any concurrent `start()` even has a chance to run.
        self._generation += 1
        if self._token is not None:
            self._token.cancel()
        self._task_handle.cancel()
        self._task_handle = None
        self._token = None
        return True

    async def _run_stream(self, token: CancellationToken, generation: int) -> None:
        # Resolved here, not cached at construction time: `EnsureSessionReadyCommand`
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

        self._trading_client = self._trading_client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )

        is_closing = False
        client: AsyncClient | None = None
        try:
            client = await AsyncClient.create(
                api_key=resolution.credentials.api_key,
                api_secret=resolution.credentials.api_secret,
                testnet=self._events.venue.is_testnet,
            )
            bsm = BinanceSocketManager(client)

            while not token.is_cancelled() and generation == self._generation:
                try:
                    socket = bsm.futures_user_socket()
                    async with socket as stream:
                        while (
                            not token.is_cancelled() and generation == self._generation
                        ):
                            res = await stream.recv()
                            # `BUG-094` — re-checked after `await`, not just
                            # in the loop condition above: `stop()`/a new
                            # `start()` can bump `self._generation` while
                            # this coroutine was suspended waiting on
                            # `stream.recv()`.
                            if res and generation == self._generation:
                                await self._handle_message(res)
                except asyncio.CancelledError:
                    logger.info("User data stream task was cancelled.")
                    break
                except (OSError, ReadLoopClosed) as exc:
                    # `BUG-096` — `ReadLoopClosed` (a plain `Exception`,
                    # not `OSError`) is what `stream.recv()` actually
                    # raises once the library's own reconnect budget (5
                    # attempts) is exhausted and its internal read loop
                    # dies — the `except OSError` alone never caught this,
                    # the steady-state disconnect case, only a first-
                    # connect DNS/refused-connection failure. Re-entering
                    # `bsm.futures_user_socket()`/`async with socket` below
                    # genuinely revives it: `futures_user_socket()` returns
                    # the same cached `KeepAliveWebsocket`, and re-entering
                    # its `async with` calls `connect()` again, which opens
                    # a fresh websocket and restarts the read loop since
                    # `_handle_read_loop` was reset to `None` on the way out
                    # (verified by reading the library's own source).
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

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("e")
        if event_type == ORDER_TRADE_UPDATE:
            self._order_updates.on_order_trade_update(payload)
        elif event_type == ACCOUNT_UPDATE:
            await self._handle_account_update(payload)
        elif event_type == ALGO_UPDATE:
            self._order_updates.on_algo_update(payload)
        elif event_type == _LIBRARY_ERROR_EVENT:
            # `BUG-096` — before this branch existed, a connection blip
            # produced this sentinel and `_handle_message` silently
            # dropped it (matched neither `ORDER_TRADE_UPDATE` nor
            # `ACCOUNT_UPDATE`) — the app logged nothing at all for the
            # entire duration of a reconnect cycle.
            logger.warning(
                "User data stream reported a connection issue: %s (%s)",
                payload.get("m"),
                payload.get("type"),
            )

    async def _handle_account_update(self, payload: dict[str, Any]) -> None:
        if self._trading_client is None:
            # Only a direct `_handle_message` call before `_run_stream` gets here.
            logger.error("ACCOUNT_UPDATE received before the stream was ready.")
            return

        # `BUG-092` — folds *this* event's positions into the running
        # per-symbol total before summing, rather than summing only what
        # this one event reports: `account_update_position_pnls` only ever
        # covers the positions that changed in this specific message, so
        # summing it alone would silently drop every other open position's
        # uPnL from the equity sample on a multi-position account.
        self._unrealized_pnl_by_symbol.update(account_update_position_pnls(payload))

        # `EPIC-021M` §2.1 — sampled from the same stream message, no extra
        # request. `None` when this update carries no balance entry for the
        # quote asset (e.g. a position-only update) — nothing to record.
        wallet_balance = account_update_wallet_balance(payload)
        if wallet_balance is not None:
            equity_sample = EquitySample(
                captured_at=account_update_captured_at(payload),
                wallet_balance=wallet_balance,
                unrealized_pnl=sum(self._unrealized_pnl_by_symbol.values(), Decimal(0)),
            )
            self._equity_recorder.record(equity_sample)
            self._events.equity_sampled(equity_sample)
            # `BUG-095` — `DEBUG`: fires on every `ACCOUNT_UPDATE` carrying
            # a balance line, which on an active session is every fill.
            logger.debug(
                "ACCOUNT_UPDATE  equity  wallet %s  uPnL %s  total %s",
                equity_sample.wallet_balance,
                equity_sample.unrealized_pnl,
                equity_sample.total,
            )

        generation = self._generation
        for symbol in account_update_changed_symbols(payload):
            # `BOT-145` — off the loop: `get_positions()` blocks on REST I/O.
            # `BUG-094` — re-fenced after the await: `stop()`/`start()` may
            # bump the generation mid-call; a stale handler must not write.
            positions = await asyncio.to_thread(
                self._trading_client.get_positions, symbol
            )
            if generation != self._generation:
                return
            reconcile_position_state(
                self._session_state, symbol, has_position=bool(positions)
            )
            if positions:
                self._events.position_changed(positions[0])
                # `BUG-095` — `DEBUG`, same reasoning as the equity line
                # above: one per changed position, per `ACCOUNT_UPDATE`.
                logger.debug(
                    "ACCOUNT_UPDATE  %s  pos %s  entry %s  uPnL %s",
                    symbol,
                    positions[0].position_amt,
                    positions[0].entry_price,
                    positions[0].unrealized_pnl,
                )
            else:
                # `BUG-086` — closing is a real change, carried by a dedicated
                # event: `LivePosition` forbids `position_amt == 0`, so
                # `PositionChangedEvent` cannot. `BUG-095` — `DEBUG` as above.
                self._events.position_closed(symbol)
                logger.debug("ACCOUNT_UPDATE  %s  position closed", symbol)
