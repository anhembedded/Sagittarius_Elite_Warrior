"""Historical load + live-stream lifecycle for the Trading screen's single
chart (`EPIC-021I`).

@details Mirrors `dashboard/stream_lifecycle_controller.py`'s shape,
narrowed: one chart, one symbol/interval at a time, no auto-sync progress
bar (this screen has none — plain log lines instead), no Load History /
Start Live distinction (the chart is always live while this screen is
open).

Never touches `TradingPresenter.view` — every method here runs on a
background thread (submitted via `IThreadManager`), and `ChartCard` is a
`QWidget`; mutating it off the Qt main thread is the exact class of defect
`BUG-031` documents. Results are reported back only through the
`emit_*` callables, each bound to one of `TradingPresenter`'s own Qt
signals — the same boundary `StreamLifecycleController` uses.

Owns no async action-id/cancellation bookkeeping of its own
(`async-ui-action-rule.md` §2): the `CancellationToken` is created and
reset by `TradingPresenter`, passed in on every call.

**Ownership (`BOT-126`).** `ILiveStreamService` is reference-counted per
`(symbol, interval)` across owners — this coordinator always identifies
itself as `_STREAM_OWNER` ("trading"), so `stop()` here only ever releases
THIS screen's own subscription, never Dev Board's, even if both are live
on the same or different symbols at once. Stop-then-start on a
symbol/interval change (`start()`/`stop()` below) is kept for clarity, not
because it is required — `subscribe()` already replaces this owner's
prior subscription outright.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

#: How many candles the chart asks for on a (re)load — a fixed depth, not
#: derived from anything (unlike Dev Board's `_compute_fetch_limit()`,
#: which grows with enabled indicator scripts — this screen has none,
#: EPIC-021I's own scope decision).
_HISTORY_CANDLE_LIMIT = 500

#: `BOT-126` — this screen's own identity on `ILiveStreamService`. Exactly
#: one `TradingPresenter`/`ChartCoordinator` is ever alive at once, so a
#: fixed string is enough (no need for a per-instance id).
_STREAM_OWNER = "trading"


class ChartCoordinator:
    """@brief Loads history and keeps the Trading screen's one `ChartCard`
    live for whatever symbol/interval is currently selected."""

    def __init__(
        self,
        *,
        thread_manager: IThreadManager,
        dispatcher: IDispatcher,
        emit_history_ready: Callable[[str, list, list, list], None],
        emit_load_finished: Callable[[], None],
        emit_stream_started: Callable[[str], None],
        emit_stream_failed: Callable[[str], None],
        emit_log: Callable[[str], None],
    ) -> None:
        self._thread_manager = thread_manager
        self._dispatcher = dispatcher
        self._emit_history_ready = emit_history_ready
        self._emit_load_finished = emit_load_finished
        self._emit_stream_started = emit_stream_started
        self._emit_stream_failed = emit_stream_failed
        self._emit_log = emit_log

    def start(
        self,
        symbol: str,
        interval_str: str,
        token: CancellationToken,
        *,
        go_live: bool = False,
    ) -> None:
        """Submits the chart load for `symbol`/`interval_str`.

        @param go_live When `False` (the default) this reads **local history
        only** — one `GetHistoricalKlinesQuery` against the app's own
        database, no network. When `True` it also syncs from Binance and
        opens the websocket.

        @details `BUG-107`: opening a screen is not a request to go on the
        network. `go_live` defaults to `False` so a caller that forgets the
        argument gets the quiet behaviour, not a live stream — the failure
        this parameter exists to prevent should not be reachable by
        omission.
        """
        self._thread_manager.submit(self._run, symbol, interval_str, token, go_live)

    def stop(self) -> None:
        """Fast and synchronous — same as Dev Board's own
        `_on_stop_stream`, which never submits this to the thread pool
        either. Owner-scoped (`BOT-126`): releases only this screen's own
        subscription."""
        self._dispatcher.dispatch(
            StopLiveStreamCommand, StopLiveStreamCommand(owner=_STREAM_OWNER)
        )

    def _run(
        self,
        symbol: str,
        interval_str: str,
        token: CancellationToken,
        go_live: bool,
    ) -> None:
        try:
            interval = TimeFrame(interval_str)

            if not go_live:
                self._emit_log(
                    f"Loading {symbol} data from the local database "
                    "(not connected live — enable trading to connect)."
                )

            if go_live:
                self._emit_log(f"Syncing {symbol} data from Binance...")
                self._dispatcher.dispatch(
                    SyncMarketDataCommand,
                    SyncMarketDataCommand(
                        symbols=[symbol],
                        interval=interval,
                        cancellation_requested=token.is_cancelled,
                    ),
                )
                if token.is_cancelled():
                    return

            self._load_history(symbol, interval)
            if token.is_cancelled():
                return

            if go_live:
                self._start_stream(symbol, interval)
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._emit_stream_failed(f"System error: {exc}")
        finally:
            self._emit_load_finished()

    def _load_history(self, symbol: str, interval: TimeFrame) -> None:
        query = GetHistoricalKlinesQuery(
            symbol=[symbol],
            interval=interval,
            limit=_HISTORY_CANDLE_LIMIT,
            order_by_desc=True,
        )
        response = self._dispatcher.dispatch(GetHistoricalKlinesQuery, query)
        results = getattr(response, "data", response) if response else {}
        klines = results.get(symbol, []) if isinstance(results, dict) else []
        if not klines:
            self._emit_log(f"No historical data for {symbol}.")
            return
        ordered = list(reversed(klines))
        # `EPIC-022E` — the raw `MarketData` rows ride along beside the
        # chart-shaped tuples. `StrategyOverlayCoordinator` replays the
        # strategy over real candles (it reads `close_time`/`close_price`),
        # which `map_klines`' 5-tuples no longer carry; re-fetching them
        # for the overlay would be a second identical query.
        self._emit_history_ready(
            symbol, map_klines(ordered), map_volume(ordered), ordered
        )

    def _start_stream(self, symbol: str, interval: TimeFrame) -> None:
        self._emit_log(f"Opening live stream for {symbol}...")
        cmd = StartLiveStreamCommand(
            owner=_STREAM_OWNER, symbols=[symbol], interval=interval
        )
        response = self._dispatcher.dispatch(StartLiveStreamCommand, cmd)
        if response and getattr(response, "success", True):
            self._emit_stream_started(f"Streaming live data for {symbol}.")
        else:
            message = getattr(response, "message", "Unknown error")
            self._emit_stream_failed(f"Could not open live stream: {message}")
