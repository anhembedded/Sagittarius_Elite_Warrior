"""
Benchmark harness for IndicatorScriptRunner.feed_all() that goes through REAL
Qt machinery instead of simulating it.

Why this exists (BOT-036): an earlier ad-hoc benchmark measured a hand-rolled
`list(x_data)` copy standing in for "what Qt does on emit" — that is a real
cost, but nothing confirms it is the SAME cost PySide6's actual queued
cross-thread signal marshaling pays (a Python list is typically boxed as a
PyObject-backed QVariant, where a queued emit likely just bumps a refcount,
not a deep copy). This harness sidesteps the question entirely by using the
real thing: a QObject with signals declared identically to
DashboardPresenter's, and the real `ThreadManager` (the actual
`IThreadManager` implementation the presenter submits background work to,
not a raw `threading.Thread`).

Two scenarios, because they have different cost profiles and BOT-036 found
the second one is the more impactful of the two in the real app:
  - `run_background_path`: mirrors `_run_load_history`/`_run_sync_and_start`
    — feed_all() runs on a ThreadManager worker, signals cross to the main
    thread via a queued connection.
  - `run_main_thread_path`: mirrors `_on_history_prepended` (BOT-035's
    load-more-on-scroll) — feed_all() runs directly on the main thread, so
    every emit is a synchronous direct-connection call.
"""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass

from PySide6 import QtCore
from sagittarius_engine.infrastructure.thread_manager import ThreadManager

from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.runner import (
    IndicatorScriptRunner,
)


class SignalBridge(QtCore.QObject):
    """Declared identically to DashboardPresenter's four script signals
    (`ui_indicator_data_signal`, `ui_script_region_signal`,
    `ui_script_info_signal`, `ui_script_marker_signal`). If the presenter's
    signal signatures ever change, this must change with them, or the
    benchmark silently stops representing the real app."""

    line = QtCore.Signal(str, list, list)
    region = QtCore.Signal(str, list)
    info = QtCore.Signal(str, list)
    markers = QtCore.Signal(str, list)


@dataclass
class FeedBenchmarkResult:
    elapsed_seconds: float
    emit_count: int
    peak_traced_memory_bytes: int
    #: Candles actually fed — echoed back so a report can be built without
    #: threading the original count through separately.
    candle_count: int = 0
    scenario: str = ""


def _build_runner(
    registry: IndicatorScriptRegistry,
    script_keys: list[str],
    bridge: SignalBridge,
    counts: dict[str, int],
) -> IndicatorScriptRunner:
    """One counting slot per channel, wired to the real signals — emit_count
    is the number of times Qt actually dispatched a connected slot, not the
    number of times `feed()` internally decided to call `self._emit_*`."""

    def _count(channel: str) -> Callable[..., None]:
        def _handler(*_args: object) -> None:
            counts[channel] = counts.get(channel, 0) + 1

        return _handler

    bridge.line.connect(_count("line"))
    bridge.region.connect(_count("region"))
    bridge.info.connect(_count("info"))
    bridge.markers.connect(_count("markers"))

    runner = IndicatorScriptRunner(
        registry=registry,
        emit_line=bridge.line.emit,
        emit_region=bridge.region.emit,
        emit_info=bridge.info.emit,
        emit_markers=bridge.markers.emit,
        on_error=lambda _msg: None,
    )
    runner.rebuild(script_keys)
    return runner


def run_background_path(
    app: QtCore.QCoreApplication,
    registry: IndicatorScriptRegistry,
    script_keys: list[str],
    candles: list[MarketData],
) -> FeedBenchmarkResult:
    """Submits feed_all() to a real ThreadManager worker — same call path as
    DashboardPresenter._run_load_history. `future.result()` blocks until the
    background call returns, by which point every queued-connection emit has
    already been POSTED to the main thread's event queue (posting happens
    synchronously inside `.emit()`, only delivery is deferred) — the
    following `processEvents()` drains exactly that queue, so the measured
    window covers the full round trip: background compute + cross-thread
    marshaling + main-thread dispatch."""
    bridge = SignalBridge()
    counts: dict[str, int] = {}
    runner = _build_runner(registry, script_keys, bridge, counts)
    thread_manager = ThreadManager(max_workers=1)

    tracemalloc.start()
    start = time.perf_counter()
    try:
        future = thread_manager.submit(runner.feed_all, candles)
        future.result()
        app.processEvents()
    finally:
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        thread_manager.shutdown(wait=True)

    return FeedBenchmarkResult(
        elapsed_seconds=elapsed,
        emit_count=sum(counts.values()),
        peak_traced_memory_bytes=peak,
        candle_count=len(candles),
        scenario="background (Load History / Start Live)",
    )


def run_main_thread_path(
    registry: IndicatorScriptRegistry,
    script_keys: list[str],
    candles: list[MarketData],
) -> FeedBenchmarkResult:
    """Calls feed_all() directly on the main thread — same call path as
    DashboardPresenter._on_history_prepended (BOT-035 load-more-on-scroll).
    Same-thread emit resolves to a direct connection, so every emit executes
    synchronously inside feed_all() itself; no event-loop drain needed."""
    bridge = SignalBridge()
    counts: dict[str, int] = {}
    runner = _build_runner(registry, script_keys, bridge, counts)

    tracemalloc.start()
    start = time.perf_counter()
    try:
        runner.feed_all(candles)
    finally:
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    return FeedBenchmarkResult(
        elapsed_seconds=elapsed,
        emit_count=sum(counts.values()),
        peak_traced_memory_bytes=peak,
        candle_count=len(candles),
        scenario="main thread (load-more-on-scroll)",
    )
