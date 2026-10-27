"""`EPIC-047D` — the SSH adapter of `ILinkTransport`, on `asyncssh` (SSH record D1).

The connection lives in an asyncio loop on a thread of its own (`link-ssh-loop`); the callers are
plain threads and reach it only through `run_coroutine_threadsafe` and a queue. **No blocking call is
inside that loop**: every wait in a coroutine is an `await`, and the one place that waits for a lock
or a queue (`receive_line`) runs on the caller's thread. `tests/unit/support/wire/desk/` runs the loop
in debug mode against a real in-process server and fails on a slow callback.

The host's key is pinned through `known_hosts` (`ssh_connect_options.py`); a login failure is told
apart as typed errors, never parsed from text. The stderr of the bridge, which `sshd` hands over, is
logged at DEBUG: standard output is the protocol.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Final

import asyncssh
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.i_link_transport import (
    ILinkTransport,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    HostUnreachableError,
    KeyFileUnusableError,
    KeyRefusedError,
    LinkError,
    LinkLostError,
    UnknownHostKeyError,
    WrongHostKeyError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.ssh_connect_options import (
    connect_options,
    known_hosts_path,
)

logger = logging.getLogger("App.LinkSsh")

#: A write to a live pipe returns at once; a stalled one is a lost link.
_WRITE_TIMEOUT_S: Final = 10.0
_CLOSE_TIMEOUT_S: Final = 5.0


class AsyncSshTransport(ILinkTransport):
    def __init__(self, *, loop_debug: bool = False) -> None:
        self._loop_debug = loop_debug
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        #: The bridge's lines; `None` marks the end of the stream.
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._connection: asyncssh.SSHClientConnection | None = None
        self._process: asyncssh.SSHClientProcess[str] | None = None
        self._ended = False

    # -- ILinkTransport -------------------------------------------------------------------

    def open(self, profile: LinkProfile) -> None:
        loop = self._start_loop()
        pending = asyncio.run_coroutine_threadsafe(self._connect(profile), loop)
        try:
            pending.result(timeout=profile.connect_timeout_s * 2 + 5)
        except LinkError:
            self.close()
            raise
        except TimeoutError:
            self.close()
            raise HostUnreachableError(
                profile.host, profile.port, "no answer in time"
            ) from None

    def send_line(self, line: str) -> None:
        loop = self._loop
        if loop is None or self._ended:
            raise LinkLostError("the link is closed")
        pending = asyncio.run_coroutine_threadsafe(self._write(line + "\n"), loop)
        try:
            pending.result(timeout=_WRITE_TIMEOUT_S)
        except (OSError, asyncssh.Error, TimeoutError) as failure:
            raise LinkLostError(_reason_of(failure)) from failure

    def receive_line(self, timeout_s: float) -> str | None:
        try:
            item = self._lines.get(timeout=timeout_s)
        except queue.Empty:
            return None
        if item is None:
            self._lines.put(None)  # every later call learns it too
            raise LinkLostError("the host closed the connection")
        return item

    def close(self) -> None:
        self._ended = True
        loop, thread = self._loop, self._thread
        if loop is None or thread is None:
            return
        if loop.is_running():
            closing = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
            try:
                closing.result(timeout=_CLOSE_TIMEOUT_S)
            except (TimeoutError, OSError, asyncssh.Error):
                logger.debug(
                    "[link-ssh] the close did not finish cleanly", exc_info=True
                )
            loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=_CLOSE_TIMEOUT_S)
        self._lines.put(None)

    # -- the loop's thread ----------------------------------------------------------------

    def _start_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.new_event_loop()
        if self._loop_debug:
            loop.set_debug(True)
            loop.slow_callback_duration = 0.05
        started: Future[None] = Future()

        def run() -> None:
            asyncio.set_event_loop(loop)
            loop.call_soon(started.set_result, None)
            loop.run_forever()
            loop.close()

        self._loop = loop
        self._thread = threading.Thread(target=run, name="link-ssh-loop", daemon=True)
        self._thread.start()
        started.result(timeout=5.0)
        return loop

    async def _connect(self, profile: LinkProfile) -> None:
        try:
            connection = await asyncssh.connect(**connect_options(profile))  # type: ignore[arg-type]
        except asyncssh.HostKeyNotVerifiable:
            raise _host_key_error(profile) from None
        except asyncssh.PermissionDenied:
            raise KeyRefusedError(profile.host, profile.user) from None
        except asyncssh.KeyImportError as failure:
            raise KeyFileUnusableError(
                profile.key_file, _reason_of(failure)
            ) from failure
        except FileNotFoundError as failure:
            raise _missing_file_error(profile, failure) from failure
        except (OSError, asyncssh.Error, TimeoutError) as failure:
            raise HostUnreachableError(
                profile.host, profile.port, _reason_of(failure)
            ) from failure
        self._connection = connection
        try:
            self._process = await connection.create_process(encoding="utf-8")
        except (OSError, asyncssh.Error) as failure:
            connection.close()
            raise HostUnreachableError(
                profile.host, profile.port, _reason_of(failure)
            ) from failure
        asyncio.get_running_loop().create_task(self._pump(self._process))
        asyncio.get_running_loop().create_task(self._drain_stderr(self._process))

    async def _pump(self, process: asyncssh.SSHClientProcess[str]) -> None:
        try:
            async for line in process.stdout:
                self._lines.put(line.rstrip("\r\n"))
        except (OSError, asyncssh.Error):
            logger.debug("[link-ssh] reading ended with an error", exc_info=True)
        finally:
            self._lines.put(None)

    async def _drain_stderr(self, process: asyncssh.SSHClientProcess[str]) -> None:
        try:
            async for line in process.stderr:
                logger.debug("[link-ssh] host stderr: %s", line.rstrip())
        except (OSError, asyncssh.Error):
            return

    async def _write(self, text: str) -> None:
        process = self._process
        if process is None:
            raise LinkLostError("the link is closed")
        process.stdin.write(text)
        await process.stdin.drain()

    async def _shutdown(self) -> None:
        if self._process is not None:
            self._process.close()
        if self._connection is not None:
            self._connection.close()
            await self._connection.wait_closed()


def _host_key_error(profile: LinkProfile) -> LinkError:
    """Unknown host or wrong key: told apart by whether the pinned file names the host at all."""
    path = known_hosts_path(profile)
    if not _file_names_host(path, profile):
        return UnknownHostKeyError(profile.host, profile.port, str(path))
    return WrongHostKeyError(profile.host, str(path))


def _file_names_host(path: Path, profile: LinkProfile) -> bool:
    try:
        known = asyncssh.read_known_hosts(str(path))
    except (OSError, asyncssh.KeyImportError):
        return False
    trusted, _ca, _revoked, _x509, _x509_ca, _x509_revoked, *_ = known.match(
        profile.host, "", profile.port
    )
    return bool(trusted)


def _missing_file_error(profile: LinkProfile, failure: FileNotFoundError) -> LinkError:
    if (
        profile.key_file
        and Path(profile.key_file).expanduser().name == Path(str(failure.filename)).name
    ):
        return KeyFileUnusableError(profile.key_file, "no such file")
    return UnknownHostKeyError(
        profile.host, profile.port, str(known_hosts_path(profile))
    )


def _reason_of(failure: BaseException) -> str:
    text = str(failure).strip()
    return text[:120] if text else type(failure).__name__
