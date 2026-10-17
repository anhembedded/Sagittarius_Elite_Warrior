"""`EPIC-038J`, `EPIC-038K`, `EPIC-038L` - `bot stop|pause|resume|start|edit` from a second process to a real `run` host (decision O4, channel A).

@details Real processes, because a lock, a directory's owner and a listening socket belong to
processes. The host is `main.py run` over the fake exchange with a bot file that its first boot
turns RECOVERING; the operator is `main.py bot ...` in its own process, a read-only copy beside the
host. What is proved here that the in-process journeys cannot: the verbs cross a real process
boundary, the command directory is made private by the host, a refusal comes back in the screen's
words with its exit code, nothing is sent when no host runs, and **the host listens on no port**.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import stat
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.grid_fake_exchange import (
    GRID,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.run_process_support import (
    children_to_reap,
    fake_exchange,
    start_child,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.test_run_process_beside_other_processes import (
    NO_PRICE_STREAMS,
    SPOT_TESTNET_CREDENTIALS,
    _state_of,
)
from Sagittarius_Elite_Warrior.tests.run_host_child import (
    CHILD_SCRIPT,
    DEFAULT_CREDENTIALS,
    START_BUDGET_SECONDS,
    RunChild,
    child_environment,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sanity"))
from binance_fake_server import FakeServerUrls

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="reads /proc for the sockets and the owner-only mode bits are POSIX",
)

_REPO_PARENT = Path(__file__).resolve().parents[4]
_CREDENTIALS = {**DEFAULT_CREDENTIALS, **SPOT_TESTNET_CREDENTIALS}
_TCP_LISTEN = "0A"


@pytest.fixture
def exchange() -> Iterator[FakeServerUrls]:
    with fake_exchange() as urls:
        yield urls


@pytest.fixture
def started(exchange: FakeServerUrls) -> Iterator[list[RunChild]]:
    with children_to_reap() as children:
        yield children


def _seed_a_bot_that_ran(
    data_root: Path,
    bot_id: str,
    state: BotLifecycleState = BotLifecycleState.RUNNING,
) -> Path:
    """A bot (RUNNING unless said) with a run behind it (`run_started_at`): a stop has a run to close."""
    bots = data_root / "state" / "bots"
    started = datetime(2026, 10, 1, tzinfo=UTC)
    bot = Bot(
        BotId(bot_id),
        BotDefinition("grid one", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT", GRID),
        BotLifecycle(state, run_started_at=started),
        started,
    )
    JsonBotStore(bots).save(StoredBot(bot, dict(encode_runtime(GridRuntime(())))))
    return bots


def _bot(
    data_root: Path, urls: FakeServerUrls, *args: str
) -> subprocess.CompletedProcess[str]:
    """`main.py bot <args> --json` in its own process, as the operator would type it."""
    return subprocess.run(
        [sys.executable, "-c", CHILD_SCRIPT, "bot", *args, "--json"],
        cwd=str(_REPO_PARENT),
        capture_output=True,
        text=True,
        timeout=START_BUDGET_SECONDS,
        check=False,
        env=child_environment(data_root, urls, _CREDENTIALS),
    )


def _listening_tcp_ports(pid: int) -> list[str]:
    """The TCP sockets in LISTEN state that this process owns, as `address:port` hex."""
    mine = {
        link.removeprefix("socket:[").removesuffix("]")
        for fd in os.listdir(f"/proc/{pid}/fd")
        if (link := _readlink(Path(f"/proc/{pid}/fd/{fd}"))).startswith("socket:[")
    }
    listening: list[str] = []
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        if not table.exists():  # a kernel without IPv6 has no tcp6 table
            continue
        for row in table.read_text(encoding="utf-8").splitlines()[1:]:
            fields = row.split()
            if fields[3] == _TCP_LISTEN and fields[9] in mine:
                listening.append(fields[1])
    return listening


def _readlink(path: Path) -> str:
    try:
        return str(path.readlink())
    except OSError:
        return ""


def test_the_listening_socket_detector_sees_a_socket_this_process_listens_on() -> None:
    """The proof the empty list below means something: the same function finds a real listener."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()

        found = _listening_tcp_ports(os.getpid())

    assert len(found) == 1


def _host(started: list[RunChild], data_root: Path, urls: FakeServerUrls) -> RunChild:
    child = start_child(
        started,
        data_root,
        urls,
        "--skip-preflight",
        "--health-interval",
        "1",
        patch=NO_PRICE_STREAMS,
        credentials=_CREDENTIALS,
    )
    child.wait_for_stdout("[host] BOOTING -> SERVING")
    child.wait_for_stdout("[control] accepting")
    return child


def test_a_second_process_stops_a_bot_on_the_running_host_and_the_host_listens_on_no_port(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    bots = _seed_a_bot_that_ran(tmp_path, "aaaaaa")
    host = _host(started, tmp_path, exchange)
    directory = tmp_path / "state" / "control"
    assert _state_of(bots, "aaaaaa") is BotLifecycleState.RECOVERING

    refused = _bot(tmp_path, exchange, "pause", "aaaaaa")
    stopped = _bot(tmp_path, exchange, "stop", "aaaaaa")

    assert _listening_tcp_ports(host.pid) == [], "the host opens no port for control"
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert refused.returncode == int(ExitCode.USAGE), refused.stdout + refused.stderr
    assert "aaaaaa" in refused.stderr and "PAUSED" not in refused.stdout
    assert stopped.returncode == int(ExitCode.SUCCESS), stopped.stdout + stopped.stderr
    document = json.loads(stopped.stdout)
    assert document["schema"] == "sew.bot-control/1"
    assert document["data"]["status"] == "done"
    assert _state_of(bots, "aaaaaa") is BotLifecycleState.STOPPED, (
        "the screen's Stop ran, after opening the order session a restart leaves closed"
    )
    audit = [
        json.loads(line)
        for line in (directory / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [(e["verdict"], e["action"]) for e in audit] == [
        ("received", "pause"),
        ("refused", "pause"),
        ("received", "stop"),
        ("executed", "stop"),
    ]
    assert os.listdir(directory) == ["audit.jsonl"], "commands are removed"

    host.send(signal.SIGTERM)
    assert host.finish() == int(ExitCode.SUCCESS), host.evidence


def test_a_second_process_start_of_a_halted_bot_is_refused_in_the_screens_words(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """`EPIC-038K`: `bot start` crosses the process boundary like the other verbs. A HALTED bot is
    refused toward `run --resume-halted` before the exchange is read, the file is not changed, and
    the audit lists the refusal."""
    bots = _seed_a_bot_that_ran(tmp_path, "bbbbbb", BotLifecycleState.HALTED)
    host = _host(started, tmp_path, exchange)
    directory = tmp_path / "state" / "control"

    refused = _bot(tmp_path, exchange, "start", "bbbbbb")

    assert refused.returncode == int(ExitCode.USAGE), refused.stdout + refused.stderr
    assert "--resume-halted" in refused.stderr
    assert _state_of(bots, "bbbbbb") is BotLifecycleState.HALTED
    audit = [
        json.loads(line)
        for line in (directory / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [(e["verdict"], e["action"]) for e in audit] == [
        ("received", "start"),
        ("refused", "start"),
    ]

    host.send(signal.SIGTERM)
    assert host.finish() == int(ExitCode.SUCCESS), host.evidence


def test_a_second_process_edits_a_stopped_bot_beside_a_running_one_on_the_host(
    started: list[RunChild], tmp_path: Path, exchange: FakeServerUrls
) -> None:
    """`EPIC-038L`: `bot edit` crosses the process boundary. The STOPPED bot's parameters change on its
    own file and it lands on DRAFT, the other bot is not touched, a malformed `--set` is a usage error
    before anything is written, and a bot that is not at rest is refused in the screen's words."""
    bots = _seed_a_bot_that_ran(tmp_path, "cccccc", BotLifecycleState.STOPPED)
    _seed_a_bot_that_ran(tmp_path, "aaaaaa")
    host = _host(started, tmp_path, exchange)
    directory = tmp_path / "state" / "control"
    assert _state_of(bots, "aaaaaa") is BotLifecycleState.RECOVERING

    malformed = _bot(tmp_path, exchange, "edit", "cccccc", "--set", "lower")
    edited = _bot(
        tmp_path,
        exchange,
        "edit",
        "cccccc",
        "--set",
        "lower=47000",
        "--set",
        "upper=53000",
    )
    refused = _bot(tmp_path, exchange, "edit", "aaaaaa", "--set", "lower=47000")

    assert malformed.returncode == int(ExitCode.USAGE), (
        malformed.stdout + malformed.stderr
    )
    assert "--set 1" in malformed.stderr
    assert edited.returncode == int(ExitCode.SUCCESS), edited.stdout + edited.stderr
    message = json.loads(edited.stdout)["data"]["message"]
    assert "lower 48000 -> 47000" in message and "upper 52000 -> 53000" in message
    config = JsonBotStore(bots).load(BotId("cccccc")).bot.definition.config
    assert (config["lower"], config["upper"]) == ("47000", "53000")
    assert _state_of(bots, "cccccc") is BotLifecycleState.DRAFT
    assert refused.returncode == int(ExitCode.USAGE), refused.stdout + refused.stderr
    assert "DRAFT or STOPPED" in refused.stderr
    assert _state_of(bots, "aaaaaa") is BotLifecycleState.RECOVERING
    audit = [
        json.loads(line)
        for line in (directory / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [(e["verdict"], e["action"]) for e in audit] == [
        ("received", "edit"),
        ("executed", "edit"),
        ("received", "edit"),
        ("refused", "edit"),
    ]

    host.send(signal.SIGTERM)
    assert host.finish() == int(ExitCode.SUCCESS), host.evidence


def test_with_no_host_running_the_verb_says_so_exits_ten_and_writes_nothing(
    tmp_path: Path, exchange: FakeServerUrls
) -> None:
    _seed_a_bot_that_ran(tmp_path, "aaaaaa")

    result = _bot(tmp_path, exchange, "stop", "aaaaaa")

    assert result.returncode == int(ExitCode.HOST_NOT_RUNNING), (
        result.stdout + result.stderr
    )
    assert "No host is running" in result.stderr
    assert not (tmp_path / "state" / "control").exists()
    assert exchange.requests == [], "nothing reached the exchange"
