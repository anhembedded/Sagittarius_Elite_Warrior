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

**No dispatcher.** `EPIC-025` PR 1.1a moved the candle read onto
`IHistoricalKlines` and 1.1b the stream onto `IMarketStream`, which between
them were everything this coordinator dispatched. The parameter went with
the last of them: one nobody uses still tells every caller and every test
that this class talks to the bus.

**Ownership (`BOT-126`).** `IMarketStream` is reference-counted per
`(symbol, interval)` across owners — this coordinator always identifies
itself as `_STREAM_OWNER` ("trading"), so `stop()` here only ever releases
THIS screen's own subscription, never Dev Board's, even if both are live
on the same or different symbols at once. Stop-then-start on a
symbol/interval change (`start()`/`stop()` below) is kept for clarity, not
because it is required — the port already replaces this owner's prior
subscription outright, which its contract suite pins.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

#: How many candles the chart asks for on a (re)load — a fixed depth, not
#: derived from anything (unlike Dev Board's `_compute_fetch_limit()`,
#: which grows with enabled indicator scripts — this screen has none,
#: EPIC-021I's own scope decision).
_HISTORY_CANDLE_LIMIT = 500

#: `BOT-126` — this screen's own identity on `IMarketStream`. Exactly
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
        market_data_sync: IMarketDataSync,
        historical_klines: IHistoricalKlines,
        market_stream: IMarketStream,
        emit_history_ready: Callable[[str, list, list, list], None],
        emit_load_finished: Callable[[], None],
        emit_stream_started: Callable[[str], None],
        emit_stream_failed: Callable[[str], None],
        emit_log: Callable[[str], None],
    ) -> None:
        self._thread_manager = thread_manager
        self._market_data_sync = market_data_sync
        self._historical_klines = historical_klines
        self._market_stream = market_stream
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
        only** — one `IHistoricalKlines.load()` against the app's own
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
        # The outcome is deliberately ignored: `success=False` here means
        # "this screen held no subscription", which is the ordinary case for
        # an unconditional `stop()` and not something to tell the user about.
        self._market_stream.stop(_STREAM_OWNER)

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
                self._market_data_sync.sync(
                    MarketDataSyncRequest(
                        symbols=(symbol,),
                        interval=interval,
                        cancellation_requested=token.is_cancelled,
                    )
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
        # `EPIC-025` PR 1.1 — one call where there were five steps. This used
        # to build `GetHistoricalKlinesQuery` with `symbol=[symbol]` — a list
        # of one, to make the handler return a dict — then unwrap it through
        # `getattr(response, "data", response)`, a `.get(symbol, [])` and an
        # `isinstance(results, dict)` guard. Every one of those existed only
        # because the handler's return type changed with the argument's
        # runtime type (`architecture-rule.md` §2.1). The port asks for one
        # symbol and gets that symbol's rows.
        newest_first_rows = self._historical_klines.load(
            symbol, interval, limit=_HISTORY_CANDLE_LIMIT, newest_first=True
        )
        if not newest_first_rows:
            self._emit_log(f"No historical data for {symbol}.")
            return
        # `newest_first=True` is how the limit keeps the most RECENT candles;
        # the chart draws chronologically, so it is reversed here exactly as
        # before.
        ordered = list(reversed(newest_first_rows))
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
        # `EPIC-025` PR 1.1b — one typed call where there were four steps.
        # The `getattr(response, "success", True)` this replaces reported
        # success for any object without that field, `None` included: a
        # stream that never opened told the user it was streaming.
        outcome = self._market_stream.start(_STREAM_OWNER, [symbol], interval)
        if outcome.success:
            self._emit_stream_started(f"Streaming live data for {symbol}.")
        else:
            self._emit_stream_failed(f"Could not open live stream: {outcome.message}")
