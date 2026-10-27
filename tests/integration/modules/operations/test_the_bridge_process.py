"""`EPIC-047C` - the bridge as `sshd` starts it: a real process on pipes, beside a data root that has no host.

@details Real processes, because a socket, an exit status and a process that outlives its peer belong
to processes. What is proved here that the in-process session tests cannot: the entry point wires the
real store reader, facts reader and control door; the process speaks the protocol on its standard
streams and nothing else; it holds **no socket of any kind** (read from `/proc`, the precedent of
`test_control_of_a_running_host_process.py`); it is given no key and no network and needs neither; a
different build gets "refused" and exit status 3; a peer that froze with no end of file is let go.
The restricted `authorized_keys` line cannot be tested here (it is `sshd`'s); that check is the owner's
run on the VPS, recorded in the task.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import repo_root
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
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.shell.link_version import link_app_version
from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_ENDED,
    EXIT_IDLE,
    EXIT_REFUSED,
    IDLE_WATCHDOG_S,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import (
    PROTOCOL,
    Hello,
    hello_of,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.grid_fake_exchange import (
    GRID,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    document,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_core import (
    minimal_request,
)

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="reads /proc for the process's sockets",
)

_REPO_PARENT = repo_root().parent
_WAIT_S = 20.0
_REQUEST_ID = "0123456789abcdef0123456789abcdef"
_STARTED = datetime(2026, 10, 1, tzinfo=UTC)


def _hello() -> Hello:
    return hello_of(link_roots(), link_app_version())


def _environment(data_root: Path) -> dict[str, str]:
    """No exchange key, no keyring, no network settings: the bridge must not need any."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            ("BINANCE_", "SEW_", "CREDENTIALS_DIRECTORY", "HTTP", "http")
        )
    }
    env.update(
        SEW_DATA_ROOT=str(data_root),
        PYTHONPATH=str(_REPO_PARENT),
        PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring",
    )
    return env


class BridgeChild:
    def __init__(self, data_root: Path) -> None:
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "Sagittarius_Elite_Warrior.src.shell.link_bridge_main",
            ],
            cwd=str(_REPO_PARENT),
            env=_environment(data_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._read_stdout, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def say(self, message: dict[str, object]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def next(self) -> dict[str, object]:
        line = self._lines.get(timeout=_WAIT_S)
        assert line is not None, "the bridge closed its output"
        message = json.loads(line)
        assert isinstance(message, dict)
        return message

    def next_of(self, kind: str) -> dict[str, object]:
        while True:
            message = self.next()
            if message["type"] == kind:
                return message

    def call(self, call_id: int, method: str, **params: object) -> dict[str, object]:
        self.say({"type": "call", "id": call_id, "method": method, "params": params})
        while True:
            message = self.next()
            if message.get("id") == call_id:
                return message

    def sockets(self) -> list[str]:
        """Every socket the process holds, of any family: TCP, UDP, Unix, netlink."""
        found = []
        for fd in Path(f"/proc/{self.process.pid}/fd").iterdir():
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target.startswith("socket:"):
                found.append(target)
        return found

    def greet(self, hello: Hello | None = None) -> None:
        assert self.next()["type"] == "hello"
        self.say({"type": "hello", **(hello or _hello()).to_wire()})

    def hang_up(self) -> int:
        assert self.process.stdin is not None
        self.process.stdin.close()
        return self.process.wait(timeout=_WAIT_S)

    def kill(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=_WAIT_S)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()


@contextmanager
def _bridge(data_root: Path) -> Iterator[BridgeChild]:
    child = BridgeChild(data_root)
    try:
        yield child
    finally:
        child.kill()


def _bot(bot_id: str, state: BotLifecycleState) -> StoredBot:
    bot = Bot(
        BotId(bot_id),
        BotDefinition("grid one", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT", GRID),
        BotLifecycle(state, run_started_at=_STARTED),
        _STARTED,
    )
    return StoredBot(bot, dict(encode_runtime(GridRuntime(()))))


def _a_data_root(tmp_path: Path) -> tuple[Path, JsonBotStore]:
    state = tmp_path / "state"
    store = JsonBotStore(state / "bots")
    store.save(_bot("aaaaaa", BotLifecycleState.RUNNING))
    written = document(7)
    (state / "host-facts.json").write_bytes(
        JsonHostFactsCodec().encode(
            replace(
                written, header=replace(written.header, written_at=datetime.now(UTC))
            )
        )
    )
    return tmp_path, store


def test_a_session_reads_the_hosts_files_follows_a_write_and_holds_no_socket(
    tmp_path: Path,
) -> None:
    data_root, store = _a_data_root(tmp_path)
    roots = link_roots()
    with _bridge(data_root) as bridge:
        bridge.greet()
        assert bridge.next()["type"] == "welcome"
        snapshot = bridge.call(1, "snapshot")["data"]
        assert isinstance(snapshot, dict)
        assert list(snapshot["revisions"]) == ["aaaaaa"]
        assert roots.decode(snapshot["list"]).bots[0].state is BotLifecycleState.RUNNING  # type: ignore[attr-defined]
        assert (snapshot["facts"]["state"], snapshot["facts"]["revision"]) == (
            "live",
            7,
        )  # type: ignore[index]

        assert bridge.call(2, "subscribe")["type"] == "result"
        store.save(_bot("aaaaaa", BotLifecycleState.STOPPED))
        event = bridge.next_of("event")
        assert (event["kind"], event["bot_id"], event["revision"]) == (
            "bot",
            "aaaaaa",
            2,
        )
        assert roots.decode(event["bot"]).state is BotLifecycleState.STOPPED  # type: ignore[attr-defined]

        assert bridge.sockets() == []
        bridge.say({"type": "ping"})
        assert bridge.next_of("pong")
        assert bridge.hang_up() == EXIT_ENDED


def test_a_command_with_no_host_running_is_answered_not_running_and_writes_nothing(
    tmp_path: Path,
) -> None:
    data_root, _ = _a_data_root(tmp_path)
    request = link_roots().encode("sew.host-control-request/1", minimal_request())
    with _bridge(data_root) as bridge:
        bridge.greet()
        bridge.next_of("welcome")

        answer = bridge.call(
            1, "command", request_id=_REQUEST_ID, request=request, wait_s=1
        )

        reply = link_roots().decode(answer["data"]["reply"])  # type: ignore[index]
        assert reply.status.value == "not_running"  # type: ignore[attr-defined]
        assert not (data_root / "state" / "control").exists()
        assert bridge.hang_up() == EXIT_ENDED


def test_a_different_build_is_refused_with_status_3_and_the_hello_comes_first(
    tmp_path: Path,
) -> None:
    data_root, _ = _a_data_root(tmp_path)
    with _bridge(data_root) as bridge:
        bridge.greet(Hello(PROTOCOL, "0.0.1", _hello().root_hashes))

        refusal = bridge.next()

        assert refusal["type"] == "refused"
        assert "sudo sew-update" in str(refusal["words"])
        assert bridge.process.wait(timeout=_WAIT_S) == EXIT_REFUSED


def test_a_desktop_that_froze_with_no_end_of_file_leaves_no_bridge_after_the_watchdog(
    tmp_path: Path,
) -> None:
    """DERISK R5: a half-open link left 1 bridge after 10 s without a heartbeat, 0 with a 6 s watchdog."""
    data_root, _ = _a_data_root(tmp_path)
    with _bridge(data_root) as bridge:
        bridge.greet()
        bridge.next_of("welcome")

        status = bridge.process.wait(timeout=IDLE_WATCHDOG_S * 3)

        assert status == EXIT_IDLE
        assert bridge.process.poll() is not None


def test_the_bridge_imports_no_application_no_qt_and_no_network_library(
    tmp_path: Path,
) -> None:
    """The slim entry point (`link_bridge_main`): the wire layer, two `link.py` files and the lock probe."""
    program = (
        "import sys, Sagittarius_Elite_Warrior.src.shell.link_bridge_main\n"
        "print(json.dumps(sorted(sys.modules)))"
    ).replace("print(json", "import json; print(json")
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(_REPO_PARENT),
        env=_environment(tmp_path),
        capture_output=True,
        text=True,
        timeout=_WAIT_S,
        check=True,
    )
    loaded = set(json.loads(result.stdout))

    forbidden = {
        "PySide6",
        "socket",
        "ssl",
        "http",
        "urllib3",
        "requests",
        "keyring",
        "sagittarius_engine.app",
        "Sagittarius_Elite_Warrior.src.shell.composition_root",
        "Sagittarius_Elite_Warrior.src.main",
        "Sagittarius_Elite_Warrior.src.modules.bots.module",
        "Sagittarius_Elite_Warrior.src.modules.operations.module",
        "Sagittarius_Elite_Warrior.src.modules.trading.module",
        "Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly",
    }
    assert sorted(loaded & forbidden) == []
