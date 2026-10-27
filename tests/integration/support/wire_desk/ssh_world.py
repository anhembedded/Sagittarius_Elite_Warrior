"""`EPIC-047D` - a real SSH server on loopback with the real `BridgeSession` behind it, and a minimal SSH agent.

What the adapter's tests need and a double cannot give: `asyncssh` on both ends, a host key to pin,
a key to authorize, and a connection to cut abruptly. The server runs in its own thread and loop; a
test starts it, reads its port, and stops it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import struct
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import asyncssh
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProfile,
    ReconnectPolicy,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    BridgeSession,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    VERSION,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    BridgeHost,
)

LOOPBACK = "127.0.0.1"
_TICK_S = 0.02


class Keys:
    """A host key, a client key written to a file, and the files the server and client read."""

    def __init__(self, directory: Path) -> None:
        self.host_key = asyncssh.generate_private_key("ssh-ed25519")
        self.client_key = asyncssh.generate_private_key("ssh-ed25519")
        self.stranger_key = asyncssh.generate_private_key("ssh-ed25519")
        self.client_file = directory / "id_ed25519"
        self.client_file.write_bytes(self.client_key.export_private_key())
        self.authorized = directory / "authorized_keys"
        self.authorized.write_bytes(self.client_key.export_public_key())
        self.known_hosts = directory / "known_hosts"

    def pin(self, port: int, *, key: asyncssh.SSHKey | None = None) -> None:
        """Pin the host's key (or another key, for a wrong-key test) for `127.0.0.1:port`."""
        line = (key or self.host_key).export_public_key().decode().strip()
        self.known_hosts.write_text(f"[{LOOPBACK}]:{port} {line}\n")

    def profile(self, port: int, **fields: object) -> LinkProfile:
        base: dict[str, object] = {
            "name": "loopback",
            "host": LOOPBACK,
            "port": port,
            "key_source": KeySource.KEY_FILE,
            "key_file": str(self.client_file),
            "known_hosts": str(self.known_hosts),
            "connect_timeout_s": 5.0,
            "reconnect": ReconnectPolicy(first_delay_s=0.0, max_delay_s=0.0),
        }
        return LinkProfile(**(base | fields))  # type: ignore[arg-type]


class _Server(asyncssh.SSHServer):
    def __init__(self, owner: SshHost) -> None:
        self._owner = owner

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        self._owner.connections.append(conn)


class SshHost:
    """The VPS: sshd's login and the bridge, in one loop on one thread."""

    def __init__(self, keys: Keys, host: BridgeHost) -> None:
        self.keys, self.host = keys, host
        self.connections: list[asyncssh.SSHServerConnection] = []
        self.bridge_sessions = 0
        self.port = 0
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="test-sshd", daemon=True)
        self._server: asyncssh.SSHAcceptor | None = None

    def start(self) -> SshHost:
        self._thread.start()
        self.port = asyncio.run_coroutine_threadsafe(self._listen(), self._loop).result(
            10
        )
        return self

    def stop(self) -> None:
        asyncio.run_coroutine_threadsafe(self._close(), self._loop).result(10)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(5)

    def cut_all(self) -> None:
        """Every connection ends without a goodbye (the cable pulled)."""
        done = asyncio.run_coroutine_threadsafe(self._abort(), self._loop)
        done.result(10)

    # -- on the server's loop -------------------------------------------------------------

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        self._loop.close()

    async def _listen(self) -> int:
        self._server = await asyncssh.create_server(
            lambda: _Server(self),
            LOOPBACK,
            0,
            server_host_keys=[self.keys.host_key],
            authorized_client_keys=str(self.keys.authorized),
            process_factory=self._bridge,
            gss_host=None,
            encoding="utf-8",
        )
        return int(self._server.sockets[0].getsockname()[1])

    async def _close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        await self._abort()

    async def _abort(self) -> None:
        for connection in self.connections:
            connection.abort()
        self.connections.clear()

    async def _bridge(self, process: asyncssh.SSHServerProcess[str]) -> None:
        self.bridge_sessions += 1
        loop = asyncio.get_running_loop()

        def emit(message: dict[str, object]) -> None:
            process.stdout.write(json.dumps(message) + "\n")

        session = BridgeSession(
            ROOTS, VERSION, self.host.ports(), emit, lambda work: work()
        )
        session.begin(loop.time())
        try:
            while session.exit_code is None:
                try:
                    line = await asyncio.wait_for(process.stdin.readline(), _TICK_S)
                except TimeoutError:
                    session.tick(loop.time())
                    continue
                if not line:
                    session.ended()
                    break
                session.feed(line, loop.time())
                session.tick(loop.time())
        except (asyncssh.Error, OSError):
            return
        process.exit(session.exit_code or 0)


# -- an SSH agent holding one key -----------------------------------------------------------

_IDENTITIES, _SIGN, _ANSWER_IDS, _SIGNATURE, _FAILURE = 11, 13, 12, 14, 5


def _string(data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + data


@contextlib.contextmanager
def ssh_agent_holding(key: asyncssh.SSHKey, directory: Path) -> Iterator[str]:
    """A Unix-socket SSH agent that answers for `key`; the socket's path."""
    path = str(directory / "agent.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(4)
    stopping = threading.Event()

    def serve() -> None:
        while not stopping.is_set():
            try:
                client, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=_answer, args=(client, key), daemon=True).start()

    thread = threading.Thread(target=serve, name="test-agent", daemon=True)
    thread.start()
    try:
        yield path
    finally:
        stopping.set()
        server.close()
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)
        thread.join(2)


def _answer(client: socket.socket, key: asyncssh.SSHKey) -> None:
    with client:
        while True:
            head = _read(client, 4)
            if head is None:
                return
            body = _read(client, struct.unpack(">I", head)[0])
            if body is None:
                return
            reply = _reply_to(body, key)
            client.sendall(_string(reply))


def _read(client: socket.socket, count: int) -> bytes | None:
    data = b""
    while len(data) < count:
        chunk = client.recv(count - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def _reply_to(body: bytes, key: asyncssh.SSHKey) -> bytes:
    kind = body[0]
    if kind == _IDENTITIES:
        return (
            bytes([_ANSWER_IDS])
            + struct.pack(">I", 1)
            + _string(key.public_data)
            + _string(b"test")
        )
    if kind == _SIGN:
        blob_length = struct.unpack(">I", body[1:5])[0]
        rest = body[5 + blob_length :]
        data_length = struct.unpack(">I", rest[:4])[0]
        signature = key.sign(rest[4 : 4 + data_length], key.sig_algorithms[0])
        return bytes([_SIGNATURE]) + _string(signature)
    return bytes([_FAILURE])


def on_a_thread(call: Callable[[], None]) -> threading.Thread:
    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    return thread
