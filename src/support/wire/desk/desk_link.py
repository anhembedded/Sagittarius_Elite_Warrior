"""`EPIC-047D` — one live connection: a transport, the desktop's protocol, and the thread that reads.

`DeskLink` is what the rest of the desktop holds. `connect` blocks until the bridge has welcomed this
build (call it from a worker, not the UI thread); `call` and `command` block for one answer; events
and the end of the link go to the two callbacks, on the reader thread (the UI hands them across with
`UiThreadRelay`). One `DeskLink` is one connection and is never reused: a reconnect builds a new one
through `LinkSupervisor`, and with it a fresh `RevisionGate` (047C's rule: never keep a gate across a
reconnect).

@par A command is never sent twice
A read is cheap to ask again; a command may move real money. When the link is cut with a command
unanswered, its caller gets `CommandInFlightLostError(request_id)` and `DeskLink` sends nothing by itself.
The caller asks again with the **same** request id on the next connection, and the host answers from
its audit and runs it once (`ICommandDoor.send`).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.i_link_transport import (
    ILinkTransport,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    CallFailedError,
    CallTimedOutError,
    CommandInFlightLostError,
    LinkError,
    LinkLostError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_protocol import (
    HANDSHAKE_TIMEOUT_S,
    DeskProtocol,
    IDeskListener,
    LinkTimings,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import Hello

logger = logging.getLogger("App.LinkDesk")

#: Longest the reader waits for a line before it looks at the clock (ping, silence).
READ_SLICE_S: Final = 0.1
DEFAULT_CALL_TIMEOUT_S: Final = 10.0
#: Past the bridge's own `wait_s` for a command: it answers by then, or the link is in trouble.
COMMAND_GRACE_S: Final = 5.0


@dataclass(frozen=True, slots=True)
class _Pending:
    future: Future[dict[str, object]]
    method: str
    #: The request id of a command; `None` for a read.
    command_id: str | None


class DeskLink(IDeskListener):
    def __init__(
        self,
        transport: ILinkTransport,
        own_hello: Hello,
        *,
        on_event: Callable[[dict[str, object]], None],
        on_closed: Callable[[LinkError | None], None],
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transport = transport
        self._on_event = on_event
        self._on_closed = on_closed
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        self._lock = threading.RLock()
        self._pending: dict[int, _Pending] = {}
        self._ready: Future[LinkTimings] = Future()
        self._data_as_of: datetime | None = None
        self._protocol = DeskProtocol(own_hello, self._write, self)
        self._reader: threading.Thread | None = None

    @property
    def data_as_of(self) -> datetime | None:
        """When the last answer or event came (UTC); `None` before any."""
        return self._data_as_of

    @property
    def is_up(self) -> bool:
        return self._protocol.is_ready

    @property
    def unanswered(self) -> int:
        """How many calls wait for an answer."""
        return len(self._pending)

    # -- the caller's side ----------------------------------------------------------------

    def connect(self, profile: LinkProfile) -> LinkTimings:
        """Open the transport and finish the greeting.

        @raise LinkError the typed reason the link did not come up."""
        try:
            self._transport.open(profile)
        except LinkError:
            self._transport.close()  # a failed open may have left a half-built session
            raise
        with self._lock:
            self._protocol.begin(self._monotonic())
        self._reader = threading.Thread(
            target=self._read_loop, name="link-desk-reader", daemon=True
        )
        self._reader.start()
        try:
            return self._ready.result(timeout=HANDSHAKE_TIMEOUT_S + COMMAND_GRACE_S)
        except FutureTimeout:
            self.close()
            raise LinkLostError(
                "the bridge did not welcome this desktop in time"
            ) from None
        except LinkError:
            self.close()
            raise

    def call(
        self,
        method: str,
        params: dict[str, object] | None = None,
        *,
        timeout_s: float = DEFAULT_CALL_TIMEOUT_S,
    ) -> dict[str, object]:
        """A read.

        @raise LinkLostError the link is down or went down before the answer.
        @raise CallFailedError the bridge refused the call.
        @raise CallTimedOutError no answer in time."""
        return self._ask(method, params or {}, None, timeout_s)

    def command(
        self, request_id: str, request: dict[str, object], wait_s: float
    ) -> dict[str, object]:
        """A command, under an id the caller made and keeps (`ICommandDoor.send`).

        @raise CommandInFlightLostError the link went down with this command unanswered: its outcome is
            unknown and it is not sent again by this class."""
        params: dict[str, object] = {
            "request_id": request_id,
            "request": request,
            "wait_s": wait_s,
        }
        return self._ask("command", params, request_id, wait_s + COMMAND_GRACE_S)

    def close(self) -> None:
        with self._lock:
            self._protocol.close()
        self._transport.close()
        reader = self._reader
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=2.0)

    # -- IDeskListener (the reader thread, under the lock) ---------------------------------

    def on_ready(self, timings: LinkTimings) -> None:
        self._ready.set_result(timings)

    def on_result(self, call_id: int, data: dict[str, object]) -> None:
        self._data_as_of = self._wall_clock()
        pending = self._pending.pop(call_id, None)
        if pending is not None:
            pending.future.set_result(data)

    def on_call_error(self, call_id: int, code: str, message: str) -> None:
        pending = self._pending.pop(call_id, None)
        if pending is not None:
            pending.future.set_exception(CallFailedError(code, message))

    def on_event(self, event: dict[str, object]) -> None:
        self._data_as_of = self._wall_clock()
        self._on_event(event)

    def on_closed(self, reason: LinkError | None) -> None:
        lost = (
            reason
            if reason is not None
            else LinkLostError("the desktop closed the link")
        )
        if not self._ready.done():
            self._ready.set_exception(lost)
        pending, self._pending = self._pending, {}
        for item in pending.values():
            item.future.set_exception(
                CommandInFlightLostError(item.command_id) if item.command_id else lost
            )
        logger.info(
            "[link-desk] closed: %s (%d calls unanswered)",
            "desktop" if reason is None else type(reason).__name__,
            len(pending),
        )
        self._on_closed(reason)

    # -- internals ------------------------------------------------------------------------

    def _ask(
        self,
        method: str,
        params: dict[str, object],
        command_id: str | None,
        timeout_s: float,
    ) -> dict[str, object]:
        future: Future[dict[str, object]] = Future()
        with self._lock:
            try:
                call_id = self._protocol.call(method, params, self._monotonic())
            except LinkLostError as failure:
                if command_id is None:
                    raise
                # A write that raised may still have reached the host (asyncssh buffers it before it
                # drains): the command's outcome is unknown, not "never sent".
                raise CommandInFlightLostError(command_id) from failure
            self._pending[call_id] = _Pending(future, method, command_id)
        try:
            return future.result(timeout=timeout_s)
        except FutureTimeout:
            with (
                self._lock
            ):  # the caller has its answer (none); a late one is dropped, not kept
                self._pending.pop(call_id, None)
                self._protocol.forget(call_id)
            raise CallTimedOutError(method, timeout_s) from None

    def _write(self, message: dict[str, object]) -> None:
        self._transport.send_line(json.dumps(message, separators=(",", ":")))

    def _read_loop(self) -> None:
        while not self._protocol.is_closed:
            try:
                line = self._transport.receive_line(READ_SLICE_S)
            except LinkLostError as lost:
                with self._lock:
                    self._protocol.lost(lost)
                return
            with self._lock:
                now = self._monotonic()
                if line is not None:
                    self._protocol.feed(line, now)
                self._protocol.tick(now)
