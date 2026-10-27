"""`EPIC-047D` - what the desktop link's tests share: the real `BridgeSession` behind a transport that is a few queues.

The bridge is not imitated: the desktop talks to `BridgeSession` itself, with the fake ports of
`bridge_world`, so a change to either end's wire form fails here. A transport can be cut (`cut`),
made half open (`go_silent`) or refuse to open (`fail_open`), and the test moves no clock it has
not injected.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    BridgeSession,
    SessionPorts,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.i_link_transport import (
    ILinkTransport,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    LinkError,
    LinkLostError,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import Hello, hello_of
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    VERSION,
    FakeBots,
    FakeDoor,
    FakeFacts,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
    minimal_bot,
)

PROFILE = LinkProfile(name="vps", host="vps.example")
DESK_HELLO = hello_of(ROOTS, VERSION)
_END = object()


def _on_a_thread(work: Callable[[], None]) -> None:
    """A command waits on the host's door on a thread of its own, as in `serve`."""
    threading.Thread(target=work, daemon=True).start()


class BridgeHost:
    """One host: the bots and facts a bridge reads, and the bridges it has started."""

    def __init__(self) -> None:
        self.bots = FakeBots(full_bot(), minimal_bot())
        self.facts = FakeFacts()
        self.door = FakeDoor()
        self.started = 0

    def ports(self) -> SessionPorts:
        return SessionPorts(self.bots, self.facts, self.door)


class BridgeTransport(ILinkTransport):
    """`ILinkTransport` onto a real `BridgeSession`, in this process.

    `receive_line` moves the bridge's clock first (as `serve` does), then waits on a queue."""

    def __init__(
        self,
        host: BridgeHost,
        *,
        bridge_hello: Hello | None = None,
        idle_watchdog_s: float | None = None,
    ) -> None:
        self.host = host
        self.sent: list[dict[str, object]] = []
        self.opened = False
        self.closed = False
        self._fail_open: LinkError | None = None
        self._bridge_hello = bridge_hello
        self._watchdog = idle_watchdog_s
        self._out: queue.Queue[object] = queue.Queue()
        self._lock = threading.Lock()
        self._cut = False
        self._silent = False
        self._session: BridgeSession | None = None

    def fail_open(self, error: LinkError) -> None:
        self._fail_open = error

    def cut(self) -> None:
        """The pipe breaks: the next read and write raise `LinkLostError`."""
        self._cut = True
        self._out.put(_END)

    def go_silent(self) -> None:
        """A half-open link: writes are accepted and swallowed, nothing ever comes back."""
        self._silent = True

    @property
    def session(self) -> BridgeSession:
        assert self._session is not None
        return self._session

    # -- ILinkTransport -------------------------------------------------------------------

    def open(self, profile: LinkProfile) -> None:
        if self._fail_open is not None:
            raise self._fail_open
        timings: dict[str, float] = (
            {} if self._watchdog is None else {"idle_watchdog_s": self._watchdog}
        )
        self._session = BridgeSession(
            ROOTS,
            VERSION,
            self.host.ports(),
            self._from_bridge,
            _on_a_thread,
            **timings,
        )
        if self._bridge_hello is not None:
            self._session._hello = self._bridge_hello  # a bridge of another build
        self.host.started += 1
        self.opened = True
        with self._lock:
            self._session.begin(time.monotonic())

    def send_line(self, line: str) -> None:
        if self._cut or self.closed:
            raise LinkLostError("the pipe is broken")
        self.sent.append(json.loads(line))
        if self._silent:
            return
        with self._lock:
            self.session.feed(line, time.monotonic())

    def receive_line(self, timeout_s: float) -> str | None:
        if self._cut:
            raise LinkLostError("the pipe is broken")
        if not self._silent and self._session is not None:
            with self._lock:
                self._session.tick(time.monotonic())
        try:
            item = self._out.get(timeout=min(timeout_s, 0.02))
        except queue.Empty:
            return None
        if item is _END:
            self._out.put(_END)
            raise LinkLostError("the pipe is broken")
        assert isinstance(item, str)
        return item

    def close(self) -> None:
        self.closed = True

    # -- the bridge's side ----------------------------------------------------------------

    def _from_bridge(self, message: dict[str, object]) -> None:
        if not self._silent:
            self._out.put(json.dumps(message))

    def sent_of(self, kind: str) -> list[dict[str, object]]:
        return [m for m in self.sent if m["type"] == kind]
