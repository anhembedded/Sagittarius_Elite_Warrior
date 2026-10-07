"""`EPIC-029` ADR D15 — history and a live stream for one chart: a desk's
(`EPIC-021I`, `EPIC-028M`) or a bot's (`EPIC-029G`).

@details It moved here from trading's desk so a bot's chart uses the same
code instead of a copy (`fix-bug-rule.md` §1). Its candles come through
`ICandleFeed`, bound to the chart's market, so support imports no module.

Never touches the chart's widget — every method but `stop()` runs on a
worker thread (submitted through the injected `IThreadManager`), and
`ChartCard` is a `QWidget`; mutating it off the Qt main thread is the class
of defect `BUG-031` documents. Results go back only through
`LiveChartCallbacks`, each bound to one of the owning chart's Qt signals.

Owns no async action-id or cancellation bookkeeping of its own
(`async-ui-action-rule.md` §2): the owning chart creates and resets the
`CancellationToken` and passes it on every call.

**A cancelled load says nothing (`BUG-150`).** Every callback emits on the
owning chart, and a chart is cancelled before it is replaced or deleted (a
closed Market tab is `deleteLater`'d), so once the token is cancelled no
callback runs: not a log line, not the history, not `load_finished`. The
chart settles a request it cancelled itself (`LiveCandleChart._restart`);
`load_finished` carries the request's token so a settle that was already on
its way is matched to its own request.

**Ownership (`BOT-126`).** The stream is reference-counted per
`(symbol, interval)` across owners; this coordinator always names its own
`stream_owner` (`desk.<venue>`, `bot.<id>`), so `stop()` releases only this
chart's subscription, never another chart's, even on the same symbol.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import failure_detail
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandlesUnavailableError,
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.cancellable_report import (
    report_unless_cancelled,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_callbacks import (
    LiveChartCallbacks,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

#: How many candles a chart asks for on a (re)load: a fixed depth, since
#: these charts draw no indicator script whose warm-up would need more.
HISTORY_CANDLE_LIMIT = 500

logger = logging.getLogger("App.LiveChartCoordinator")


class LiveChartCoordinator:
    """@brief Loads history and keeps one `ChartCard` live for whatever
    symbol and interval its chart shows."""

    def __init__(
        self,
        thread_manager: IThreadManager,
        feed: ICandleFeed,
        callbacks: LiveChartCallbacks,
        stream_owner: str,
    ) -> None:
        """@param stream_owner This chart's identity on the stream
        (`BOT-126`), one per chart and required: with one shared owner,
        opening one desk's chart replaced the other's subscription (the PR 300
        epic review)."""
        self._thread_manager = thread_manager
        self._feed = feed
        self._callbacks = callbacks
        self._stream_owner = stream_owner

    def start(
        self,
        symbol: str,
        interval_str: str,
        token: CancellationToken,
        *,
        go_live: bool = False,
    ) -> None:
        """Submits the chart load for `symbol`/`interval_str`.

        @param go_live When `False` (the default) this reads **local history**,
        and only when nothing is stored fetches it from the exchange (a read of
        public candles, `BUG-172`); it opens no stream. When `True` it always
        syncs from the exchange and opens the stream.

        @details `BUG-107`: opening a screen is not a request to go live.
        `go_live` defaults to `False` so a caller that forgets the argument gets
        the quiet behaviour, not a live stream. An empty store is the one case
        that reaches the network at rest: a chart with no candles must say why or
        fill itself, never sit empty (`BUG-172`).
        """
        self._thread_manager.submit(self._run, symbol, interval_str, token, go_live)

    def stop(self) -> None:
        """Fast and synchronous, on the caller's thread. Owner-scoped
        (`BOT-126`): releases only this chart's own subscription. Holding none
        is the ordinary case for an unconditional `stop()`, not an error."""
        self._feed.stop_stream(self._stream_owner)

    def _run(
        self,
        symbol: str,
        interval_str: str,
        token: CancellationToken,
        go_live: bool,
    ) -> None:
        report = _Reporter(self._callbacks, token)
        try:
            interval = TimeFrame(interval_str)
            if go_live:
                report.log(f"Syncing {symbol} data from Binance...")
                if not self._sync(symbol, interval, token, report):
                    self._draw(symbol, interval, self._read(symbol, interval), report)
                    return
                if token.is_cancelled():
                    return
                rows = self._read(symbol, interval)
            else:
                report.log(
                    f"Loading {symbol} data from the local database "
                    "(not live — use Go live to connect)."
                )
                rows = self._read(symbol, interval)
                if not rows:
                    rows = self._fetch_what_is_missing(symbol, interval, token, report)
            self._draw(symbol, interval, rows, report)
            if token.is_cancelled():
                return
            if go_live:
                self._start_stream(symbol, interval, report)
        except Exception as exc:
            logger.warning("[live-chart] load of %s failed", symbol, exc_info=True)
            report.stream_failed(
                "The chart could not be loaded. Try again.", failure_detail(exc)
            )
        finally:
            report.load_finished()

    def _fetch_what_is_missing(
        self,
        symbol: str,
        interval: TimeFrame,
        token: CancellationToken,
        report: _Reporter,
    ) -> list:
        """`BUG-172`: a chart opened at rest on an empty store used to draw
        nothing and say so only in a log line. It now fetches the history from its
        venue's market first — a read of public candles, no stream, no order —
        and reads again; a chart that still has nothing says why, in words."""
        report.log(
            f"No {interval.value} candles of {symbol} are stored; fetching them "
            "from the exchange (no live stream)."
        )
        fetched = self._sync(
            symbol, interval, token, report, newest=HISTORY_CANDLE_LIMIT
        )
        if not fetched or token.is_cancelled():
            return []
        rows = self._read(symbol, interval)
        if not rows:
            report.load_failed(
                f"The exchange has no {interval.value} candles of {symbol} for "
                "this period (a testnet keeps a short history).",
                "",
            )
        return rows

    def _sync(
        self,
        symbol: str,
        interval: TimeFrame,
        token: CancellationToken,
        report: _Reporter,
        *,
        newest: int | None = None,
    ) -> bool:
        """Fetches what is missing; `False` once the failure has been told. A
        sync that is part of going live fails the stream (the chart goes to Error);
        one that only fills a chart at rest (`newest` given) fails the load."""
        failed = report.stream_failed if newest is None else report.load_failed
        try:
            self._feed.sync(symbol, interval, token.is_cancelled, newest=newest)
        except CandlesUnavailableError as refusal:
            # `BUG-172`: a refusal for good (a testnet's missing timeframe or
            # symbol): its reason is a sentence written for the user, said as it
            # is, with no "try again".
            reason = refusal.reason
            logger.info(
                "[live-chart] %s at %s is not served: %s",
                symbol,
                interval.value,
                reason,
            )
            failed(
                f"{reason} The chart shows the stored candles.",
                failure_detail(refusal),
            )
            return False
        except Exception as exc:
            logger.warning(
                "[live-chart] sync of %s at %s failed",
                symbol,
                interval.value,
                exc_info=True,
            )
            failed(
                f"Could not sync {symbol} at {interval.value} from the "
                "exchange. The chart shows the stored candles; try again.",
                failure_detail(exc),
            )
            return False
        return True

    def _read(self, symbol: str, interval: TimeFrame) -> list:
        return list(self._feed.load_history(symbol, interval, HISTORY_CANDLE_LIMIT))

    def _draw(
        self, symbol: str, interval: TimeFrame, ordered: list, report: _Reporter
    ) -> None:
        if not ordered:
            # `BUG-159`: nothing stored at this interval. Drawing nothing left
            # the previous interval's candles on a chart whose toolbar already
            # said this one, so the empty window is drawn too.
            report.log(
                f"No historical data for {symbol} at {interval.value}: "
                "the chart shows no candles."
            )
            report.history_ready(symbol, [], [], [])
            return
        # `EPIC-022E` — the raw `MarketData` rows ride along beside the
        # chart-shaped tuples: an overlay replays them (it reads
        # `close_time`/`close_price`, which `map_klines`' 5-tuples drop).
        report.history_ready(symbol, map_klines(ordered), map_volume(ordered), ordered)

    def _start_stream(
        self, symbol: str, interval: TimeFrame, report: _Reporter
    ) -> None:
        report.log(f"Opening live stream for {symbol}...")
        outcome = self._feed.start_stream(self._stream_owner, symbol, interval)
        if outcome.success:
            report.stream_started(f"Streaming live data for {symbol}.")
        else:
            report.stream_failed(
                f"Could not open the live stream for {symbol}. Try again.",
                outcome.message,
            )


class _Reporter:
    """One load's callbacks, silent once its token is cancelled (`BUG-150`):
    the chart they emit on may be gone (`report_unless_cancelled`)."""

    def __init__(self, callbacks: LiveChartCallbacks, token: CancellationToken) -> None:
        self._callbacks = callbacks
        self._token = token

    def log(self, text: str) -> None:
        report_unless_cancelled(self._token, self._callbacks.log, text)

    def history_ready(
        self, symbol: str, candles: list, volume: list, klines: list
    ) -> None:
        report_unless_cancelled(
            self._token, self._callbacks.history_ready, symbol, candles, volume, klines
        )

    def stream_started(self, text: str) -> None:
        report_unless_cancelled(
            self._token, self._callbacks.stream_started, self._token, text
        )

    def stream_failed(self, headline: str, detail: str) -> None:
        report_unless_cancelled(
            self._token, self._callbacks.stream_failed, self._token, headline, detail
        )

    def load_failed(self, headline: str, detail: str) -> None:
        report_unless_cancelled(
            self._token, self._callbacks.load_failed, self._token, headline, detail
        )

    def load_finished(self) -> None:
        report_unless_cancelled(self._token, self._callbacks.load_finished, self._token)
