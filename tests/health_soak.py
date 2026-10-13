"""`EPIC-038D` - the host's health machinery over fourteen simulated days (the measurement).

The task's soak: the host publishes a snapshot and a health line every interval for as long as
it lives, through a user stream that dies at every 24 h boundary and ten-minute outages in which
the exchange answers nothing; it must not stop, must not leak, and must say the truth while it
happens.

**What this is and is not.** It drives the *real* machinery - `HealthPublishing`, the publisher
and its section collector (a daemon thread per question), the probe runner, the health line
logger, the file sink and the trading section over its recorders - for 14 x 1 440 intervals of
60 s on a clock the test advances. It is not a 14-day run of the process: the Scheduler, the
bots' workers and the exchange's websocket are not here, and no wall-clock time is spent. What
it can show is that nothing the host does per interval grows - memory, threads, files - and that
the line never skips an interval, whatever the exchange is doing.

Nothing reaches an exchange: the probe is the test's, and fails during an outage as a dead route would.

**Why it runs in its own interpreter.** Inside pytest the resident size of the process grows by
tens of megabytes over the 20 160 intervals (the harness holds on to what 80 000 short-lived threads
leave), which would read as the machinery's leak and is not; a clean interpreter shows what the
host itself costs. `test_the_health_machinery_over_fourteen_simulated_days.py` runs this module
as a program and asserts on what it reports.
"""

from __future__ import annotations

import gc
import json
import logging
import sys
import tempfile
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_probe import IHealthProbe
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthProbeDescriptor,
    IHealthProbeTable,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_sink import (
    FileHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.process_memory import (
    default_process_memory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_cadence import (
    HealthCadence,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    health_lines_in,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line_logger import (
    HealthLineLogger,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_probes import (
    HealthProbes,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publisher import (
    HealthPublisher,
    HostIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publishing import (
    HealthPublishing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_section_collector import (
    HealthSectionCollector,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_sink import (
    IHealthSnapshotSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_process_memory import (
    IProcessMemory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.clock_skew_recorder import (
    ClockSkewRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.trading_health_contributor import (
    TradingHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.user_stream_recorder import (
    UserStreamRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.preflight_doubles import (
    NoPorts,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    FixedContributor,
    FixedContributors,
)

INTERVAL_S = 60
DAYS = 14
TICKS_PER_DAY = 24 * 3600 // INTERVAL_S
START = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
VENUE = TradingVenue.SPOT_TESTNET
OUTAGE_MINUTES = 10
#: Tolerances, not targets: between the end of the second day and the end of the fourteenth
#: the process may not hold more than this many megabytes or objects more, nor more threads.
RESIDENT_GROWTH_BOUND_MB = 8
OBJECT_GROWTH_BOUND = 5_000
THREAD_GROWTH_BOUND = 3


def _held(memory: IProcessMemory) -> tuple[int | None, int]:
    """Resident megabytes and live objects, after a collection."""
    gc.collect()
    return memory.resident_mb(), len(gc.get_objects())


RESULT_TAG = "SOAK_RESULT="


@dataclass(frozen=True)
class SoakResult:
    ticks: int
    lines: int
    outage_ticks: int
    snapshot_is_current: bool
    max_tick_age_s: int
    skew_was_unknown: bool
    last_skew_ms: int | None
    max_stream_down_s: int
    last_stream_down_s: int | None
    #: Megabytes resident at the end of day 2 and of day 14 (absent where /proc is).
    resident_mb: dict[int, int]
    objects: dict[int, int]
    threads_at_start: int
    threads_at_end: int
    files: list[str]


class _Clock(IOperationsClock):
    def __init__(self) -> None:
        self.at = START

    def now(self) -> datetime:
        return self.at

    def advance(self, seconds: int) -> None:
        self.at += timedelta(seconds=seconds)


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.count = 0
        self.text: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith("[health] "):
            self.count += 1
            self.text.append(
                f"2026-10-01 00:00:00,000 - {record.name} - INFO - {message}"
            )


class _HourlyFileSink(IHealthSnapshotSink):
    """The real file sink, written once a simulated hour and at the end.

    Twenty thousand atomic replaces cost more than everything else the soak does together
    and prove nothing the first few hundred do not; the sink's own tests cover one write.
    What is kept here is that the file is replaced, never appended to or left in pieces."""

    def __init__(self, path: Path) -> None:
        self._sink = FileHealthSnapshotSink(path)
        self._latest: HealthSnapshot | None = None

    def publish(self, snapshot: HealthSnapshot) -> None:
        self._latest = snapshot
        if snapshot.written_at.minute == 0:
            self._sink.publish(snapshot)

    def flush(self) -> None:
        if self._latest is not None:
            self._sink.publish(self._latest)


class _Exchange:
    """What the exchange is doing now: answering, or not."""

    def __init__(self) -> None:
        self.down = False


class _SkewProbe(IHealthProbe):
    """Asks the (simulated) exchange its time: a dead route is an exception, as in the real client."""

    def __init__(self, exchange: _Exchange, recorder: ClockSkewRecorder) -> None:
        self._exchange = exchange
        self._recorder = recorder

    @property
    def name(self) -> str:
        return "clock-skew"

    def measure(self) -> None:
        if self._exchange.down:
            self._recorder.record(VENUE.value, None)
            raise ConnectionError("no route to host")
        self._recorder.record(VENUE.value, 7)


class _Table(IHealthProbeTable):
    def __init__(self, probe: IHealthProbe) -> None:
        self._descriptor = HealthProbeDescriptor(probe.name, lambda _r: probe, "test")

    def probe_descriptors(self) -> tuple[HealthProbeDescriptor, ...]:
        return (self._descriptor,)


class _Feed(IHealthContributor):
    """The freshest candle's age, as the market-data section reports it."""

    def __init__(self) -> None:
        self.age_s = 0

    @property
    def name(self) -> str:
        return "market_data"

    def snapshot(self) -> Mapping[str, JsonValue]:
        return {"tick_age_s": self.age_s, "feeds": {}}


@contextmanager
def _heard() -> Iterator[_Lines]:
    handler = _Lines()
    logger = logging.getLogger("App.Operations")
    logger.addHandler(handler)
    previous = (logger.level, logger.propagate)
    logger.setLevel(logging.INFO)
    # As the composed app has it: records stop at `App`. Propagating 20 160 records to
    # pytest's own capture would hold every one of them and read as a leak.
    logger.propagate = False
    try:
        yield handler
    finally:
        logger.setLevel(previous[0])
        logger.propagate = previous[1]
        logger.removeHandler(handler)


def run_soak(tmp_path: Path) -> SoakResult:
    clock = _Clock()
    exchange = _Exchange()
    streams = UserStreamRecorder()
    skews = ClockSkewRecorder()
    trading = TradingHealthContributor(streams, lambda: clock.now(), skews)
    feed = _Feed()
    contributors = FixedContributors(
        FixedContributor("bots", {"states": {"RUNNING": 2, "RECOVERING": 0}}),
        feed,
        trading,
    )
    sink_path = tmp_path / "state" / "health.json"
    sink = _HourlyFileSink(sink_path)
    cadence = HealthCadence(INTERVAL_S)
    publisher = HealthPublisher(
        contributors,
        sink,
        HealthSectionCollector(5.0),
        clock,
        HostIdentity("1.0.0", 1, START, INTERVAL_S),
    )
    publishing = HealthPublishing(publisher, cadence)
    probes = HealthProbes(_Table(_SkewProbe(exchange, skews)), NoPorts(), wait_s=5.0)
    cadence.add_before(probes.run)
    cadence.add_after(HealthLineLogger(default_process_memory()))

    def stream(state: UserStreamState) -> None:
        streams.on_health(
            UserStreamHealthEvent(state=state, since=clock.now(), venue=VENUE)
        )

    threads_at_start = threading.active_count()
    ticks = 0
    memory = default_process_memory()
    resident: dict[int, int | None] = {}
    objects: dict[int, int] = {}
    outage_ticks_seen = 0
    with _heard() as heard:
        if True:
            stream(UserStreamState.CONNECTED)
            for tick in range(DAYS * TICKS_PER_DAY):
                clock.advance(INTERVAL_S)
                minute = (
                    tick % TICKS_PER_DAY
                )  # one tick is one interval of 60 s: one minute
                # The stream dies at every 24 h boundary and is back ten minutes later;
                # on the 6th and 11th days the exchange itself is out for the same ten.
                exchange.down = minute < OUTAGE_MINUTES and tick // TICKS_PER_DAY in (
                    5,
                    10,
                )
                feed.age_s = feed.age_s + INTERVAL_S if exchange.down else 0
                if tick > 0 and minute == 0:
                    stream(UserStreamState.RECONNECTING)
                if minute == OUTAGE_MINUTES:
                    stream(UserStreamState.CONNECTED)
                publishing.tick()
                ticks += 1
                outage_ticks_seen += 1 if exchange.down else 0
                if tick == 2 * TICKS_PER_DAY:
                    resident[2], objects[2] = _held(memory)
            resident[DAYS], objects[DAYS] = _held(memory)

    sink.flush()
    lines = health_lines_in("\n".join(heard.text))
    final = FileHealthSnapshotSource(sink_path).read()
    return SoakResult(
        ticks=ticks,
        lines=len(lines),
        outage_ticks=outage_ticks_seen,
        snapshot_is_current=final is not None and final.written_at == clock.now(),
        max_tick_age_s=max(line.tick_age_s or 0 for line in lines),
        skew_was_unknown=any(line.skew_ms is None for line in lines),
        last_skew_ms=lines[-1].skew_ms,
        max_stream_down_s=max(line.stream_down_s or 0 for line in lines),
        last_stream_down_s=lines[-1].stream_down_s,
        resident_mb={
            day: value for day, value in resident.items() if value is not None
        },
        objects=objects,
        threads_at_start=threads_at_start,
        threads_at_end=threading.active_count(),
        files=sorted(p.name for p in sink_path.parent.iterdir()),
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        result = run_soak(Path(directory))
    sys.stdout.write(RESULT_TAG + json.dumps(asdict(result)) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
