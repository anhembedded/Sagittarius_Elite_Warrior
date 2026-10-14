"""`main.py run` beside other processes (`EPIC-038D`): one holding the lock, one asking `status`, one killing it.

`test_run_process.py` signals a real host and reads its exit code. These tests need a second
process: a copy of the app that already holds the data root (the host must refuse to be a
read-only second one, and exit 3), `main.py status` reading a running host's snapshot and the
clock skew it measured, and a `kill -9` followed by a restart over the same bot files.

Nothing here reaches a real exchange (the child points python-binance's URLs at the fake one),
and a bot that is not at rest is given no market-data websocket (`NO_PRICE_STREAMS`).
"""

from __future__ import annotations

import json
import signal
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.instance_holder import start_holder, stop_holder
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.grid_fake_exchange import (
    GRID,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.run_process_support import (
    children_to_reap,
    fake_exchange,
    lock_is_free,
    start_child,
    status_json,
)
from Sagittarius_Elite_Warrior.tests.run_host_child import DEFAULT_CREDENTIALS, RunChild

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


#: No market-data websocket: the fake exchange speaks REST only, and a bot that is not at
#: rest asks for a price stream at boot, which would reach the real public host.
NO_PRICE_STREAMS = """
from Sagittarius_Elite_Warrior.src.modules.bots.application.services import bot_price_watch

bot_price_watch.BotPriceWatch.start = lambda self: None
bot_price_watch.BotPriceWatch.on_bot_changed = lambda self, event: None
"""

SPOT_TESTNET_CREDENTIALS = {
    "BINANCE_SPOT_TESTNET_API_KEY": "fake-spot-key-for-a-test",
    "BINANCE_SPOT_TESTNET_API_SECRET": "fake-spot-secret-for-a-test",
}


def _seed_a_running_bot(data_root: Path, bot_id: str) -> Path:
    bots = data_root / "state" / "bots"
    bot = Bot(
        BotId(bot_id),
        BotDefinition("grid one", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT", GRID),
        BotLifecycle(BotLifecycleState.RUNNING),
        datetime(2026, 10, 1, tzinfo=UTC),
    )
    JsonBotStore(bots).save(StoredBot(bot, dict(encode_runtime(GridRuntime(())))))
    return bots


def _state_of(bots: Path, bot_id: str) -> BotLifecycleState:
    return JsonBotStore(bots).load(BotId(bot_id)).bot.state


def test_status_from_a_second_process_reads_the_running_hosts_snapshot_and_its_skew(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """`EPIC-038C` left `skew_ms` null for this task to measure: the host's probe asks
    the exchange its time on the health interval, and `status` (which opens no
    connection of its own) reports what the host measured."""
    child = start_child(started, tmp_path, exchange, "--health-interval", "1")
    child.wait_for_stdout("[health] state=SERVING")

    reported = status_json(tmp_path, exchange)

    child.send(signal.SIGTERM)
    assert child.finish() == int(ExitCode.SUCCESS)
    assert reported.returncode == int(ExitCode.SUCCESS), (
        reported.stdout + reported.stderr
    )
    data = json.loads(reported.stdout)["data"]
    assert data["host"]["state"] == "running"
    assert data["host"]["host_state"] == "SERVING"
    skew = data["sections"]["trading"]["skew_ms"]
    assert isinstance(skew, int) and not isinstance(skew, bool), data["sections"][
        "trading"
    ]
    assert abs(skew) < 1000, "the fake exchange keeps this machine's time"


def test_a_plain_run_writes_no_dispatcher_query_lines(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """The Engine logs `Executing query: ...` at INFO for every dispatch, and the bots
    section dispatches two queries per snapshot. The app keeps that line out of a normal
    run's log (`BOT-178`, `Docs/OPERATIONS/LOGGING.md` §5), so the journal holds what
    happened to the bots and not how often they were read. `run` takes no `--dev`; the
    line coming back in developer mode is proved on the composition root, in
    `test_query_dispatch_is_quiet_outside_dev_mode.py`."""
    child = start_child(started, tmp_path, exchange, "--health-interval", "1")
    child.wait_for_stdout("[health] state=SERVING")
    child.wait_for_stdout("up=2s")  # at least two intervals have passed

    child.send(signal.SIGTERM)
    assert child.finish() == int(ExitCode.SUCCESS)

    lines = child.stdout.splitlines()
    health = [i for i, line in enumerate(lines) if "[health] state=SERVING" in line]
    between = lines[health[-2] + 1 : health[-1]]
    assert [line for line in between if "Executing query" in line] == [], between


def test_a_held_lock_exits_three_and_starts_nothing(
    tmp_path: Path, exchange: FakeServerUrls, started: list[RunChild]
) -> None:
    holder = start_holder(tmp_path / "state" / "instance.lock")
    try:
        child = start_child(started, tmp_path, exchange)
        code = child.finish()
    finally:
        stop_holder(holder)

    assert code == int(ExitCode.LOCK_HELD), child.stdout + child.stderr
    assert "Another copy" in child.stderr
    assert "[host]" not in child.stdout, "no host was built"
    assert exchange.requests == [], "nothing reached the exchange"
    assert not (tmp_path / "state" / "health.json").exists()


def test_sigkill_then_restart_recovers_the_bots_from_their_files(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """A kill -9 runs no handler: no snapshot says STOPPED, no worker closes. The lock
    is the operating system's, so it dies with the process (nothing to clear), the bot
    is exactly as its file says - RECOVERING since the first boot - and the next host
    names it and waits for a person (decision O2)."""
    bots = _seed_a_running_bot(tmp_path, "aaaaaa")
    credentials = {**DEFAULT_CREDENTIALS, **SPOT_TESTNET_CREDENTIALS}
    first = start_child(
        started,
        tmp_path,
        exchange,
        "--skip-preflight",
        patch=NO_PRICE_STREAMS,
        credentials=credentials,
    )
    # The health line is logged after the SERVING snapshot is written; a kill before it
    # would leave the snapshot saying BOOTING.
    first.wait_for_stdout("[health] state=SERVING")
    assert _state_of(bots, "aaaaaa") is BotLifecycleState.RECOVERING, (
        "the restart rule ran"
    )

    first.send(signal.SIGKILL)
    assert first.finish() == -signal.SIGKILL
    killed = status_json(tmp_path, exchange)

    assert "[host] SERVING -> DRAINING" not in first.stdout, "a kill runs no handler"
    assert lock_is_free(tmp_path), "the lock died with the process"
    assert killed.returncode == int(ExitCode.HOST_NOT_RUNNING), (
        killed.stdout + killed.stderr
    )
    snapshot = FileHealthSnapshotSource(tmp_path / "state" / "health.json").read()
    assert snapshot is not None and snapshot.host_state is HostState.SERVING, (
        "a crash leaves what the host last said, and a free lock is what tells `status`"
    )

    second = start_child(
        started,
        tmp_path,
        exchange,
        "--skip-preflight",
        patch=NO_PRICE_STREAMS,
        credentials=credentials,
    )
    second.wait_for_stdout("[host] BOOTING -> SERVING")
    second.wait_for_stdout("[recovering] bot aaaaaa")
    assert _state_of(bots, "aaaaaa") is BotLifecycleState.RECOVERING, (
        "the host resumed nothing"
    )
    second.send(signal.SIGTERM)

    assert second.finish() == int(ExitCode.SUCCESS), second.stdout + second.stderr
    assert _state_of(bots, "aaaaaa") is BotLifecycleState.RECOVERING
