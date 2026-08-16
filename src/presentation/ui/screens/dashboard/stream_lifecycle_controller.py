"""
@brief Manages the stream lifecycle (load history, auto-sync, start/stop live stream)
for DashboardPresenter (BOT-037 Phase 2 SRP extraction).

@details
Extracted from DashboardPresenter to isolate the asynchronous data fetching,
auto-sync orchestration, and websocket stream control into a dedicated controller,
keeping DashboardPresenter focused on FSM UI coordination and component composition.

Threading contract:
- Worker methods (_run_load_history, _run_sync_and_start, _run_load_more_history) run in background threads.
- Background workers communicate with the main thread ONLY via Qt Signal callables (emit helpers).
- Main-thread slots (_on_load_history, _on_start_stream, etc.) execute UI state updates.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from sagittarius_engine.runtime.tasks import ExclusiveAction
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .dashboard_view_model import DATETIME_FORMAT
from .kline_mapping import map_klines, map_volume

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_LOAD_MORE_BATCH_CANDLES_CONFIG_KEY = "CHART_CARD_LOAD_MORE_BATCH_CANDLES"
_DEFAULT_LOAD_MORE_BATCH_CANDLES = 75

#: BOT-033 Phase 2 — Binance-style pair: uppercase letters/digits only (no
#: domain Symbol value object exists yet to delegate this to), 5-20 chars
#: covers everything from "BTCUSDT" to a long leveraged-token pair like
#: "1000SHIBUSDT". Input is upper()'d before matching, same as every other
#: symbol entry point in this codebase (CLI handlers, SyncMarketDataCommand's
#: own validator) — a lowercase "btcusdt" is not itself an error.
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$")


def _parse_datetime_utc(raw: str) -> datetime | None:
    """Mirrors DataManagementPresenter._parse_datetime — same format, same
    UTC assumption (Binance/repository times are all UTC), so a range typed
    on one screen means the same thing typed on the other. Returns None for
    unparseable input; callers must treat that as a validation error rather
    than silently falling back to an unbounded fetch."""
    try:
        return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


class StreamLifecycleController:
    """
    @brief Controller for Dev Board historical data loading and WebSocket stream lifecycle.
    """

    def __init__(
        self,
        *,
        thread_manager: IThreadManager,
        dispatcher: IDispatcher,
        config: IConfig,
        fsm: Any,
        view_model: Any,
        script_runner: Any,
        raw_klines_by_symbol: dict[str, list],
        get_active_interval: Callable[[], str],
        set_active_interval: Callable[[str], None],
        set_active_symbol: Callable[[str], None],
        ensure_chart_cards: Callable[[list[str]], list],
        rebuild_scripts: Callable[[], None],
        compute_fetch_limit: Callable[[], int],
        get_cancellation_token: Callable[[], CancellationToken],
        reset_cancellation_token: Callable[[], CancellationToken],
        emit_history_reloaded: Callable[[str, list, list], None],
        emit_history_load_finished: Callable[[], None],
        emit_history_prepended: Callable[[str, list, list], None],
        emit_history_prepend_finished: Callable[[str, bool], None],
        emit_stream_success: Callable[[str], None],
        emit_stream_failed: Callable[[str], None],
        emit_log: Callable[[str], None],
    ) -> None:
        self._thread_manager = thread_manager
        # BOT-069 — replaces the hand-rolled historyLoading-flag +
        # FSM-LOCKED-check pair that used to be duplicated at the top of
        # both _on_load_history() and _on_start_stream() (BOT-027). One
        # instance shared by both keys makes them mutually exclusive by
        # construction — the actual TC-ASY-03 requirement (Load History and
        # Start Live must exclude each other, not just themselves).
        self._stream_actions = ExclusiveAction(thread_manager=thread_manager)
        self.dispatcher = dispatcher
        self.config = config
        self.fsm = fsm
        self._view_model = view_model
        self._script_runner = script_runner
        self._raw_klines_by_symbol = raw_klines_by_symbol
        self._get_active_interval = get_active_interval
        self._set_active_interval = set_active_interval
        self._set_active_symbol = set_active_symbol
        self._ensure_chart_cards = ensure_chart_cards
        self._rebuild_scripts = rebuild_scripts
        self._compute_fetch_limit = compute_fetch_limit
        self._get_cancellation_token = get_cancellation_token
        self._reset_cancellation_token = reset_cancellation_token

        self._emit_history_reloaded = emit_history_reloaded
        self._emit_history_load_finished = emit_history_load_finished
        self._emit_history_prepended = emit_history_prepended
        self._emit_history_prepend_finished = emit_history_prepend_finished
        self._emit_stream_success = emit_stream_success
        self._emit_stream_failed = emit_stream_failed
        self._emit_log = emit_log

    # ================================================================== #
    # Main-Thread Slot Handlers
    # ================================================================== #

    def _read_and_validate_inputs(self) -> tuple[str, str, datetime, datetime] | None:
        """
        @brief BOT-033 Phase 2 — reads Symbol/Start date/End date fresh from
        the ViewModel (same "read at click time" contract _enabled_script_keys()
        already has) and validates all three before anything is dispatched.
        @returns (symbol, interval_str, start_time, end_time) on success, or
        None after logging a user-facing error — callers must return
        immediately in that case, mirroring the historyLoading/FSM guards
        already at the top of _on_load_history/_on_start_stream.
        """
        symbol = self._view_model.symbol.strip().upper()
        if not _SYMBOL_PATTERN.match(symbol):
            self._view_model.log_model.append(
                f"Invalid symbol '{symbol}' — expected an uppercase pair like BTCUSDT.",
                level="error",
            )
            return None

        interval_str = self._get_active_interval()
        try:
            TimeFrame(interval_str)
        except ValueError:
            self._view_model.log_model.append(
                f"Invalid interval '{interval_str}'.", level="error"
            )
            return None

        start_time = _parse_datetime_utc(self._view_model.startDate)
        end_time = _parse_datetime_utc(self._view_model.endDate)
        if start_time is None or end_time is None:
            self._view_model.log_model.append(
                f"Invalid date range — expected format {DATETIME_FORMAT}.",
                level="error",
            )
            return None
        if start_time >= end_time:
            self._view_model.log_model.append(
                "Start date must be before End date.", level="error"
            )
            return None

        return symbol, interval_str, start_time, end_time

    def _on_load_history(self) -> None:
        # BOT-069 — this single check replaces the old historyLoading-flag
        # check AND the FSM-LOCKED check: the ExclusiveAction instance is
        # shared with _on_start_stream below, so it's already busy (and this
        # rejects) whenever either a load or a stream-start is in flight,
        # not just a same-key re-click.
        if not self._stream_actions.try_start("load_history"):
            self._view_model.log_model.append(
                "Wait for the current history load or live start to finish."
            )
            return

        validated = self._read_and_validate_inputs()
        if validated is None:
            self._stream_actions.finish("load_history")
            return
        symbol, interval_str, start_time, end_time = validated
        self._set_active_symbol(symbol)

        self._view_model.set_history_loading(True)
        self._view_model.log_model.append(
            "Loading historical data from local database..."
        )
        symbols = [symbol]
        self._ensure_chart_cards(symbols)
        self._rebuild_scripts()
        self._stream_actions.submit(
            "load_history",
            self._run_load_history,
            symbols,
            interval_str,
            self._compute_fetch_limit(),
            self._get_cancellation_token(),
            start_time,
            end_time,
        )

    def _on_start_stream(self) -> None:
        # Kept separate from the ExclusiveAction check below on purpose —
        # this is a DIFFERENT invariant. FSM != IDLE also covers "already
        # LIVE" / "in ERROR", states ExclusiveAction has no opinion on (its
        # slot is released the moment _run_sync_and_start finishes, whether
        # that landed on LIVE or ERROR). ExclusiveAction only knows "is a
        # start/load operation in flight right now" — ask it after this.
        if self.fsm.current_state != UIMode.IDLE:
            self._view_model.log_model.append("Already starting or running — ignoring.")
            return
        # BOT-069 — replaces the old historyLoading-flag check; shared
        # instance with _on_load_history makes the two mutually exclusive.
        if not self._stream_actions.try_start("start_stream"):
            self._view_model.log_model.append(
                "Wait for the current history load to finish before starting live stream."
            )
            return

        validated = self._read_and_validate_inputs()
        if validated is None:
            self._stream_actions.finish("start_stream")
            return
        symbol, interval_str, start_time, end_time = validated
        self._set_active_symbol(symbol)

        self._view_model.log_model.append("Starting Live Stream (Auto-Sync)...")
        self.fsm.transition_to(UIMode.LOCKED)

        symbols = [symbol]
        interval = TimeFrame(interval_str)

        chart_cards = self._ensure_chart_cards(symbols)
        self._rebuild_scripts()
        self._view_model.log_model.append(f"Prepared {len(chart_cards)} charts.")

        self._stream_actions.submit(
            "start_stream",
            self._run_sync_and_start,
            symbols,
            interval,
            interval_str,
            self._compute_fetch_limit(),
            self._get_cancellation_token(),
            start_time,
            end_time,
        )

    def _on_stream_start_success(self, msg: str) -> None:
        self._emit_log(msg)
        self.fsm.transition_to(UIMode.LIVE)

    def _on_stream_start_failed(self, msg: str) -> None:
        self._emit_log(f"Stream startup failed: {msg}")
        self.fsm.transition_to(UIMode.ERROR)

    def _on_stop_stream(self) -> None:
        self._view_model.log_model.append("Stopping Live Stream...")
        token = self._get_cancellation_token()
        token.cancel()
        self._reset_cancellation_token()
        try:
            cmd = StopLiveStreamCommand()
            self.dispatcher.dispatch(StopLiveStreamCommand, cmd)
            self._view_model.log_model.append("Live Stream stopped.")
            self.fsm.transition_to(UIMode.IDLE)
        except Exception as exc:  # noqa: BLE001
            self._view_model.log_model.append(
                f"Error while stopping: {exc}", level="error"
            )
            self.fsm.transition_to(UIMode.ERROR)

    def _on_timeframe_changed(self, timeframe: str) -> None:
        if timeframe == self._get_active_interval():
            return
        self._set_active_interval(timeframe)

        if self.fsm.current_state == UIMode.LIVE:
            self._on_stop_stream()
            self._on_start_stream()
        elif not self._stream_actions.is_running("load_history"):
            self._on_load_history()

    def fetch_older_history(self, symbol: str, oldest_timestamp: float) -> None:
        self._thread_manager.submit(
            self._run_load_more_history,
            symbol,
            self._get_active_interval(),
            oldest_timestamp,
            self.config.get(
                _LOAD_MORE_BATCH_CANDLES_CONFIG_KEY,
                _DEFAULT_LOAD_MORE_BATCH_CANDLES,
                cast=int,
            ),
            self._get_cancellation_token(),
        )

    # ================================================================== #
    # Asynchronous Background Workers
    # ================================================================== #

    def _run_load_history(
        self,
        symbols: list[str],
        interval_str: str,
        limit: int,
        token: CancellationToken,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        try:
            if token.is_cancelled() or not symbols:
                return

            query = GetHistoricalKlinesQuery(
                symbol=symbols,
                interval=interval_str,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
                order_by_desc=True,
            )
            response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            results = getattr(response, "data", response) if response else {}

            if not isinstance(results, dict):
                self._emit_log("Unexpected response format from history query.")
                return

            for symbol in symbols:
                if token.is_cancelled():
                    break

                try:
                    klines = results.get(symbol, [])
                    if not klines or not isinstance(klines, list):
                        self._emit_log(f"No historical data found for {symbol}.")
                        continue

                    ordered_klines = list(reversed(klines))
                    mapped_data = map_klines(ordered_klines)
                    volume_data = map_volume(ordered_klines)
                    self._emit_history_reloaded(symbol, mapped_data, volume_data)
                    self._raw_klines_by_symbol[symbol] = ordered_klines
                    self._script_runner.feed_all(ordered_klines)

                except Exception as exc:  # noqa: BLE001
                    self._emit_log(
                        f"Exception while loading history for {symbol}: {exc}"
                    )
        finally:
            self._emit_history_load_finished()

    def _run_load_more_history(
        self,
        symbol: str,
        interval_str: str,
        before_timestamp: float,
        limit: int,
        token: CancellationToken,
    ) -> None:
        found_more = False
        try:
            if token.is_cancelled():
                return
            end_time = datetime.fromtimestamp(before_timestamp, tz=UTC)
            query = GetHistoricalKlinesQuery(
                symbol=symbol,
                interval=interval_str,
                limit=limit,
                end_time=end_time,
                order_by_desc=True,
            )
            response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            klines = getattr(response, "data", response) if response else []

            if not isinstance(klines, list) or not klines:
                self._emit_log(f"No older data found for {symbol}.")
                return

            ordered_klines = [
                k
                for k in reversed(klines)
                if k.close_time.timestamp() < before_timestamp
            ]
            if not ordered_klines:
                self._emit_log(f"No older data found for {symbol}.")
                return
            if token.is_cancelled():
                return

            self._raw_klines_by_symbol[symbol] = (
                ordered_klines + self._raw_klines_by_symbol.get(symbol, [])
            )
            mapped_data = map_klines(ordered_klines)
            volume_data = map_volume(ordered_klines)
            self._emit_history_prepended(symbol, mapped_data, volume_data)
            found_more = True

        except RuntimeError as exc:
            self._emit_log(f"Exception while loading more history for {symbol}: {exc}")
        finally:
            self._emit_history_prepend_finished(symbol, found_more)

    def _sync_market_data(
        self,
        symbols: list[str],
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> None:
        self._emit_log("Syncing missing data from Binance...")
        sync_cmd = SyncMarketDataCommand(
            symbols=symbols,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )
        self.dispatcher.dispatch(SyncMarketDataCommand, sync_cmd)

    def _start_websocket_stream(self, symbols: list[str], interval: TimeFrame) -> None:
        self._emit_log("Opening Websocket stream...")
        cmd = StartLiveStreamCommand(symbols=symbols, interval=interval)
        response = self.dispatcher.dispatch(StartLiveStreamCommand, cmd)

        if response and getattr(response, "success", True):
            self._emit_stream_success(f"Live stream for {symbols} is running.")
        else:
            msg = getattr(response, "message", "Unknown error")
            self._emit_stream_failed(f"Failed to start: {msg}")

    def _run_sync_and_start(
        self,
        symbols: list[str],
        interval: TimeFrame,
        interval_str: str,
        limit: int,
        token: CancellationToken,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        try:
            self._sync_market_data(symbols, interval, start_time, end_time)

            if token.is_cancelled() or not symbols:
                return

            self._emit_log("Reloading historical data onto charts...")
            self._run_load_history(
                symbols, interval_str, limit, token, start_time, end_time
            )

            if token.is_cancelled():
                return

            self._start_websocket_stream(symbols, interval)

        except Exception as exc:  # noqa: BLE001
            self._emit_stream_failed(f"System error: {exc}")
