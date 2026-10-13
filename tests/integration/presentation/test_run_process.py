"""`main.py run` as a real process: signals, the lock, the pre-flight (`EPIC-038D`).

A unit test proves each piece with doubles; this proves the pieces are one program. A
child process runs `main()` exactly as `python src/main.py run` would, against the fake
exchange (`tests/sanity/binance_fake_server.py`, only the endpoint moves), and the test
sends it real signals and reads `$?`, the log it writes to stdout, the snapshot file and
the lock. Nothing here reaches a real exchange, and no order is placed, tested or
simulated: the host serves with no bot.

POSIX only for the signals (`SIGTERM`, `SIGINT`): Windows' Ctrl-Break needs a child in
a new process group and a Windows runner, and the adapter that handles it is covered
with Windows' signal numbers in `test_signal_sources.py`.
"""

from __future__ import annotations

import signal
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    health_lines_in,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.run_process_support import (
    FULL_DISK,
    HANGING_POLICY,
    children_to_reap,
    fake_exchange,
    lock_is_free,
    start_child,
    transitions,
)
from Sagittarius_Elite_Warrior.tests.run_host_child import FAKE_SECRET, RunChild

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sanity"))
from binance_fake_server import FakeServerUrls

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="sends POSIX signals; Windows' Ctrl-Break is covered by the adapter's own test",
)


@pytest.fixture
def exchange() -> Iterator[FakeServerUrls]:
    with fake_exchange() as urls:
        yield urls


@pytest.fixture
def started(exchange: FakeServerUrls) -> Iterator[list[RunChild]]:
    with children_to_reap() as children:
        yield children


@pytest.mark.parametrize(
    "which", [signal.SIGTERM, signal.SIGINT], ids=["sigterm", "sigint"]
)
def test_a_signal_to_a_real_run_process_stops_it_cleanly_and_exits_zero(
    started: list[RunChild],
    tmp_path: Path,
    exchange: FakeServerUrls,
    which: signal.Signals,
) -> None:
    child = start_child(started, tmp_path, exchange, "--health-interval", "1")
    child.wait_for_stdout("[host] BOOTING -> SERVING")
    child.wait_for_stdout("[health] state=SERVING")

    child.send(which)
    code = child.finish()

    assert code == int(ExitCode.SUCCESS), child.stdout + child.stderr
    assert transitions(child.stdout) == [
        "BOOTING -> SERVING",
        "SERVING -> DRAINING",
        "DRAINING -> STOPPED",
    ]
    assert (
        "workers closed" in child.stdout
    )  # `BotsModule.shutdown` ran: the app was stopped
    assert "Traceback" not in child.stderr + child.stdout
    snapshot = FileHealthSnapshotSource(tmp_path / "state" / "health.json").read()
    assert snapshot is not None and snapshot.host_state is HostState.STOPPED
    assert lock_is_free(tmp_path), "the lock was released"
    line = health_lines_in(child.stdout)[0]
    assert line.state is HostState.SERVING
    assert line.rss_mb is not None and line.rss_mb > 0


def test_a_second_signal_stops_at_once_and_names_what_it_left(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    child = start_child(
        started, tmp_path, exchange, "--stop-timeout", "120", patch=HANGING_POLICY
    )
    child.wait_for_stdout("[host] BOOTING -> SERVING")
    child.send(signal.SIGTERM)
    child.wait_for_stdout("[host] stop policy leave-orders")  # the drain is waiting

    began = time.monotonic()
    child.send(signal.SIGTERM)
    code = child.finish(timeout_s=30)

    assert time.monotonic() - began < 30, "it waited out the 120 s timeout"
    assert code == int(ExitCode.SUCCESS), child.stdout + child.stderr
    assert "second signal" in child.stdout
    assert "bot-x" in child.stdout and "3 orders resting" in child.stdout
    assert transitions(child.stdout)[-1] == "DRAINING -> STOPPED"
    assert lock_is_free(tmp_path)


_STUCK_APP_STOP = """
import time
from sagittarius_engine import App

def _stuck(self):
    print("APP_STOP_STARTED", flush=True)
    time.sleep(300)  # a worker that ignores its close, as app.stop() would find it

App.stop = _stuck
"""


def test_a_second_signal_while_the_app_is_closing_ends_the_process_and_says_so(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """`app.stop()` is where the 10 s-per-worker closes happen; the first signal's work
    is over by then, and an operator who presses the key again must not be ignored."""
    child = start_child(started, tmp_path, exchange, patch=_STUCK_APP_STOP)
    child.wait_for_stdout("[host] BOOTING -> SERVING")
    child.send(signal.SIGTERM)
    child.wait_for_stdout("APP_STOP_STARTED")

    began = time.monotonic()
    child.send(signal.SIGTERM)
    code = child.finish(timeout_s=30)

    assert time.monotonic() - began < 30, "the second signal was absorbed"
    assert code == int(ExitCode.SUCCESS), child.stdout + child.stderr
    assert "second signal while closing the app" in child.stdout
    assert lock_is_free(tmp_path)


def test_a_child_that_reaches_for_a_real_host_fails_the_test_that_started_it(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """`BUG-199`'s boundary is only worth having if a connect it refuses is reported even
    when the code that made it catches the error and carries on."""
    reaches_out = """
import socket
try:
    socket.create_connection(("203.0.113.9", 443), timeout=1)
except Exception:
    pass  # caught and logged by the code under test, as a real client would
"""
    child = start_child(started, tmp_path, exchange, patch=reaches_out)
    child.wait_for_stdout("[host] BOOTING -> SERVING")
    child.send(signal.SIGTERM)

    with pytest.raises(AssertionError, match="203.0.113.9"):
        child.finish()


def test_a_policy_that_outlasts_the_stop_timeout_is_given_up_on(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    child = start_child(
        started, tmp_path, exchange, "--stop-timeout", "1", patch=HANGING_POLICY
    )
    child.wait_for_stdout("[host] BOOTING -> SERVING")

    child.send(signal.SIGTERM)
    code = child.finish()

    assert code == int(ExitCode.SUCCESS), child.stdout + child.stderr
    assert "stop timeout" in child.stdout and "bot-x" in child.stdout


@pytest.mark.parametrize(
    ("arrange", "patch", "expected"),
    [
        ("key_rejected", "", ExitCode.CONFIGURATION),
        ("maintenance", "", ExitCode.EXCHANGE),
        ("full_disk", FULL_DISK, ExitCode.PREFLIGHT_FAILED),
    ],
    ids=["a rejected key is 5", "an unreachable exchange is 6", "a full disk is 4"],
)
def test_a_failed_preflight_refuses_with_the_code_a_supervisor_keys_on(
    started: list[RunChild],
    tmp_path: Path,
    exchange: FakeServerUrls,
    arrange: str,
    patch: str,
    expected: ExitCode,
) -> None:
    if arrange == "key_rejected":
        exchange.keys.known = {"some-other-key"}
    elif arrange == "maintenance":
        exchange.maintenance.on = True

    child = start_child(started, tmp_path, exchange, patch=patch)
    code = child.finish()

    assert code == int(expected), child.stdout + child.stderr
    assert "[preflight]" in child.stdout
    assert "pre-flight failed" in child.stderr
    # Refused before the bots were restored: nothing booted, nothing served.
    assert "Bots restored after start-up" not in child.stdout
    assert "[host]" not in child.stdout
    assert FAKE_SECRET not in child.stdout + child.stderr
    assert lock_is_free(tmp_path)


def test_skip_preflight_starts_where_the_preflight_would_refuse(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    exchange.keys.known = {
        "some-other-key"
    }  # `-2008` on every signed request: exit 5 without the flag
    child = start_child(started, tmp_path, exchange, "--skip-preflight")

    child.wait_for_stdout("[host] BOOTING -> SERVING")
    child.send(signal.SIGTERM)
    code = child.finish()

    assert code == int(ExitCode.SUCCESS), child.stdout + child.stderr
    assert "--skip-preflight: no check ran" in child.stdout


def test_a_host_with_nothing_configured_boots_serves_and_stops(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """The common first run: no bots, an empty data root, no credentials. (Without
    `--skip-preflight` the same run refuses with 5, `credentials-present`: that is the
    pre-flight doing its job, tested above.)"""
    child = start_child(
        started,
        tmp_path,
        exchange,
        "--skip-preflight",
        "--health-interval",
        "1",
        credentials={},
    )

    child.wait_for_stdout("[health] state=SERVING")
    child.send(signal.SIGTERM)
    code = child.finish()

    assert code == int(ExitCode.SUCCESS), child.stdout + child.stderr
    assert health_lines_in(child.stdout)[0].bots[0].count == 0
    assert exchange.requests == [], (
        "a host with no key and no bot asks the exchange for nothing"
    )
    assert "no alert channel is configured for bot events" in child.stdout


def test_a_crash_exits_one_and_the_host_does_not_retry(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    broken = """
from Sagittarius_Elite_Warrior.src.modules.operations.application import host_steps

def _boom(self):
    raise RuntimeError("a step fell over")

host_steps.WarnWhenNoAlertChannel.run = _boom
"""
    child = start_child(started, tmp_path, exchange, "--skip-preflight", patch=broken)

    code = child.finish()

    assert code == int(ExitCode.ERROR), child.stdout + child.stderr
    assert "BOOTING -> FAILED" in child.stdout
    assert child.stdout.count("[host] step alerts") == 1, (
        "no retry loop inside the host"
    )
    snapshot = FileHealthSnapshotSource(tmp_path / "state" / "health.json").read()
    assert snapshot is not None and snapshot.host_state is HostState.FAILED
    assert lock_is_free(tmp_path)
