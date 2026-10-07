import asyncio
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from binance import AsyncClient, BinanceSocketManager
from binance.ws.reconnecting_websocket import ReconnectingWebsocket
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.kline_sockets import (
    KlinePair,
    open_kline_socket,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.LiveStream")

#: Delay before retrying the WebSocket connection after an `OSError`.
_RECONNECT_DELAY_SECONDS = 5
#: `logging-rule.md` §6: `TRACE(5)`, one below `DEBUG`, on only under `--debug`.
_TRACE = 5

#: A subscription key: `(market, symbol, interval.value)` — plain `str`
#: interval, not `TimeFrame`, so two owners on the same symbol/interval hash
#: to the same key regardless of which one enters it first. The market is
#: part of the key (`EPIC-028C`): `BTCUSDT@1m` on Spot and on Futures are
#: two streams.
_StreamKey = tuple[MarketType, str, str]


@dataclass(frozen=True, slots=True)
class _RunningStream:
    """One market's live connection: the pairs it streams and how to stop it."""

    pairs: frozenset[KlinePair]
    handle: ITaskHandle
    token: CancellationToken


class BinanceWebsocketService(ILiveStreamService):
    """
    @brief Infrastructure implementation of `ILiveStreamService`.
    @details Manages one live Binance kline WebSocket connection **per
    market** (`EPIC-028C`: Spot and Futures klines come from different
    hosts, see `kline_sockets.py`) via the injected `ITaskManager`,
    reference-counted per `(market, symbol, interval)` key across every
    `owner` (`BOT-126`). Every tick is published with the market its
    connection streams, so a consumer can refuse another market's candle.

    **Reconnect-on-change trade-off (`architecture-rule.md` §7 — a price
    knowingly paid, not a bug):** whenever the *set* of active keys changes
    (an owner subscribes/releases/changes symbol), that market's
    underlying task is cancelled and respawned with the new key set —
    every owner sharing that connection loses ticks for the brief reconnect window
    (same latency already tolerated on a real network drop), even though
    none of them lose their *subscription*. Adding true incremental
    SUBSCRIBE/UNSUBSCRIBE frames on an already-open combined stream would
    avoid this, but `python-binance`'s `BinanceSocketManager` does not
    expose that conveniently — left as a follow-up if the reconnect gap
    ever proves disruptive in practice, not part of `BOT-126`'s scope.
    `test_second_owner_on_the_same_key_does_not_restart_the_task` locks
    the one case that must NOT pay this price: a second owner joining a key
    another owner already holds; and
    `test_a_change_on_one_market_leaves_the_other_markets_connection_alone`
    the other: a Spot screen changing symbol never drops Futures' ticks.
    """

    def __init__(
        self,
        event_bus: IEventBus,
        task_manager: ITaskManager,
        market_data_venue: MarketDataVenue = MarketDataVenue.MAINNET_PUBLIC,
    ) -> None:
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._market_data_venue = market_data_venue
        #: Guards `_subscriptions`/`_running` against concurrent
        #: `subscribe`/`release_owner` calls from different screens' own
        #: `IThreadManager.submit()` worker threads — same reasoning
        #: `InFlightSyncGuard` (`BOT-121`) gives its own lock.
        self._lock = threading.Lock()
        self._subscriptions: dict[_StreamKey, set[str]] = {}
        self._running: dict[MarketType, _RunningStream] = {}

    # -- ILiveStreamService ----------------------------------------------------

    def subscribe(
        self,
        owner: str,
        market_type: MarketType,
        symbols: list[str],
        interval: TimeFrame,
    ) -> bool:
        """
        @brief Replaces `owner`'s subscriptions with `symbols`/`interval` on
        `market_type`, restarting a market's connection only if that
        market's set of active keys actually changed.
        """
        with self._lock:
            self._drop_owner_locked(owner)
            for symbol in symbols:
                key = (market_type, symbol, interval.value)
                self._subscriptions.setdefault(key, set()).add(owner)
            self._apply_active_set_locked()
        return True

    def release_owner(self, owner: str) -> bool:
        """@brief Drops every key `owner` holds; never touches another
        owner's keys, even for the same `(symbol, interval)`."""
        with self._lock:
            had_any = self._drop_owner_locked(owner)
            if had_any:
                self._apply_active_set_locked()
        if not had_any:
            # DEBUG, không phải WARNING: dừng một stream chưa từng chạy là
            # trạng thái **bình thường**, không phải sự cố — cùng lý do
            # `stop_stream()` gốc từng ghi (đủ để làm đỏ bước "Run Log Scan"
            # của `ci-local.ps1` nếu là WARNING, `logging-rule.md`).
            logger.debug(
                f"release_owner({owner}) requested but it held no subscription; nothing to do."
            )
        return had_any

    def stop_all(self) -> bool:
        """@brief Tears down every subscription for every owner — Engine
        shutdown only, see this class's own docstring."""
        with self._lock:
            had_any = bool(self._subscriptions)
            self._subscriptions.clear()
            self._apply_active_set_locked()
        return had_any

    # -- Private: registry bookkeeping (caller must hold `self._lock`) --------

    def _drop_owner_locked(self, owner: str) -> bool:
        """@return True if `owner` held at least one key."""
        had_any = False
        for key in list(self._subscriptions):
            owners = self._subscriptions[key]
            if owner in owners:
                owners.discard(owner)
                had_any = True
                if not owners:
                    del self._subscriptions[key]
        return had_any

    def _apply_active_set_locked(self) -> None:
        """Restarts each market's task iff that market's desired pairs
        changed; a market nobody streams any more is stopped."""
        desired: dict[MarketType, set[KlinePair]] = {}
        for market, symbol, interval in self._subscriptions:
            desired.setdefault(market, set()).add((symbol, interval))
        for market in set(desired) | set(self._running):
            pairs = frozenset(desired.get(market, ()))
            running = self._running.get(market)
            if running is not None and running.pairs == pairs:
                continue
            if running is not None:
                running.token.cancel()
                running.handle.cancel()
                del self._running[market]
            if pairs:
                self._running[market] = self._spawn_locked(market, pairs)

    def _spawn_locked(
        self, market: MarketType, pairs: frozenset[KlinePair]
    ) -> _RunningStream:
        ordered = sorted(pairs)
        token = CancellationToken()
        logger.info(f"Starting Binance {market.value} WebSocket stream for {ordered}")
        handle = self._task_manager.spawn(
            self._run_stream(market, ordered, token),
            name=f"BinanceStream[{market.value}:"
            f"{','.join(f'{s}@{i}' for s, i in ordered)}]",
            token=token,
            critical=True,  # Đảm bảo Engine chờ task này close gracefully khi shutdown
        )
        return _RunningStream(pairs=pairs, handle=handle, token=token)

    # -- Private: the stream loop ------------------------------------------------

    async def _run_stream(
        self,
        market: MarketType,
        pairs: list[KlinePair],
        token: CancellationToken,
    ) -> None:
        """
        @brief Main async stream loop. Runs inside the Engine background task pool.
        Exits cooperatively when the CancellationToken is cancelled.
        """
        is_closing = False
        client = None
        try:
            client = await AsyncClient.create(
                testnet=resolve_testnet_flag(self._market_data_venue)
            )
            bsm = BinanceSocketManager(client)

            while not token.is_cancelled():
                try:
                    socket = open_kline_socket(bsm, market, pairs)
                    async with socket as tscm:
                        while not token.is_cancelled():
                            await self._process_socket_message(tscm, market)

                except asyncio.CancelledError:
                    logger.info("Stream task was cancelled.")
                    break
                except OSError as e:
                    if not token.is_cancelled():
                        logger.error(
                            f"WebSocket connection error: {e}. Reconnecting in "
                            f"{_RECONNECT_DELAY_SECONDS}s..."
                        )
                        await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
        except GeneratorExit:
            is_closing = True
            raise
        finally:
            if client is not None and not is_closing:
                try:
                    await client.close_connection()
                    logger.info("Binance AsyncClient connection closed.")
                except Exception as e:  # noqa: BLE001 - boundary: log and continue teardown
                    logger.warning(f"Error closing Binance client: {e}")

    async def _process_socket_message(
        self, tscm: ReconnectingWebsocket, market: MarketType
    ) -> None:
        """@brief Receives one message, unwraps the multiplex envelope, and
        emits a kline event labelled with the market its connection streams."""
        res = await tscm.recv()
        if not res:
            return

        # Multiplex stream wraps data in a "data" property
        if "data" in res:
            res = res["data"]

        if res.get("e") == "kline":
            try:
                market_data = self._parse_kline(res)
                # `BUG-113` (`BUG-042`/`BUG-095` regression), `BUG-163` —
                # fires per kline tick, several times a second per symbol;
                # `logging-rule.md` §6 puts per-tick detail at TRACE (on only
                # under `--debug`), not DEBUG, which a whole `--dev` run
                # keeps (`BUG-042`'s UI-freeze came from per-event INFO).
                if logger.isEnabledFor(_TRACE):
                    logger.log(
                        _TRACE,
                        "[Live Stream] %s | Price: %s | Vol: %s | Closed: %s",
                        market_data.symbol,
                        market_data.close_price,
                        market_data.volume,
                        market_data.is_closed,
                    )
                self._event_bus.emit(
                    MarketTickEvent(
                        market_data=market_data,
                        market_type=market,
                        market_data_venue=self._market_data_venue,
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error parsing kline message: {e} | Message: {res}")

    def _parse_kline(self, msg: dict[str, Any]) -> MarketData:
        k = msg["k"]
        return MarketData(
            symbol=k["s"],
            interval=k["i"],
            open_time=datetime.fromtimestamp(k["t"] / 1000.0, tz=UTC),
            open_price=float(k["o"]),
            high_price=float(k["h"]),
            low_price=float(k["l"]),
            close_price=float(k["c"]),
            volume=float(k["v"]),
            close_time=datetime.fromtimestamp(k["T"] / 1000.0, tz=UTC),
            quote_asset_volume=float(k["q"]),
            number_of_trades=int(k["n"]),
            taker_buy_base_asset_volume=float(k["V"]),
            taker_buy_quote_asset_volume=float(k["Q"]),
            is_closed=bool(k["x"]),
        )
