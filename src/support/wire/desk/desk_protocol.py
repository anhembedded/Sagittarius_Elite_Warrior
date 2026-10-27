"""`EPIC-047D` — the desktop's half of the bridge's conversation, driven by lines in and a clock.

The mirror of `BridgeSession` (`support/wire/bridge/bridge_session.py` has the whole protocol): it
has no I/O of its own. `feed` takes a line, `tick` takes the time, and what it says goes out through
`send`; what it learns goes to an `IDeskListener`. `DeskLink` gives it a transport and threads; a
test gives it the real `BridgeSession` and a number.

@par The conversation, from this side
  1. the bridge's **hello** arrives first. This side judges it against its own build at once and, on
     a difference, ends with `VersionDifferenceError` *without sending a hello* (no read is made on the
     host, decision D6). Otherwise it answers with its own hello immediately: the bridge waits
     only 10 s for it.
  2. **welcome** carries the bridge's heartbeat and idle watchdog; **refused** is a version
     difference or a protocol failure, in words.
  3. **calls** take ids from 1 and are answered by one `result` or `error`.
  4. **ping** goes out every third of the bridge's idle watchdog (AC6) so the bridge never idles
     out a live desktop; **pong** and every other line reset this side's own silence clock.
  5. Silence for a whole watchdog is a half-open link: this side ends it as lost, whatever the
     operating system believes.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    BridgeRefusedError,
    LinkError,
    LinkLostError,
    VersionDifferenceError,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import Hello, judge
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError

logger = logging.getLogger("App.LinkDesk")

HANDSHAKE_TIMEOUT_S: Final = 10.0
_TIMING_KEYS: Final = ("heartbeat_s", "idle_watchdog_s")


@dataclass(frozen=True, slots=True)
class LinkTimings:
    """The bridge's own cadences, from its welcome."""

    heartbeat_s: float
    idle_watchdog_s: float

    @property
    def ping_every_s(self) -> float:
        """A third of the watchdog: two pings can be lost and the bridge still hears the desktop."""
        return self.idle_watchdog_s / 3


class IDeskListener(ABC):
    """What the desktop's session reports. Called on the thread that feeds the protocol."""

    @abstractmethod
    def on_ready(self, timings: LinkTimings) -> None: ...

    @abstractmethod
    def on_result(self, call_id: int, data: dict[str, object]) -> None: ...

    @abstractmethod
    def on_call_error(self, call_id: int, code: str, message: str) -> None: ...

    @abstractmethod
    def on_event(self, event: dict[str, object]) -> None: ...

    @abstractmethod
    def on_closed(self, reason: LinkError | None) -> None:
        """Once, when the conversation is over: `None` for the desktop's own close."""


class _Phase(Enum):
    AWAIT_HELLO = auto()
    AWAIT_WELCOME = auto()
    READY = auto()
    CLOSED = auto()


class DeskProtocol:
    def __init__(
        self,
        own_hello: Hello,
        send: Callable[[dict[str, object]], None],
        listener: IDeskListener,
        *,
        handshake_timeout_s: float = HANDSHAKE_TIMEOUT_S,
    ) -> None:
        self._hello = own_hello
        self._send = send
        self._listener = listener
        self._handshake_timeout_s = handshake_timeout_s
        self._phase = _Phase.AWAIT_HELLO
        self._started_at = self._last_inbound = self._last_sent = 0.0
        self._timings: LinkTimings | None = None
        self._next_id = 0
        self._pending: set[int] = set()

    @property
    def is_ready(self) -> bool:
        return self._phase is _Phase.READY

    @property
    def is_closed(self) -> bool:
        return self._phase is _Phase.CLOSED

    @property
    def pending_ids(self) -> frozenset[int]:
        return frozenset(self._pending)

    # -- the inputs -----------------------------------------------------------------------

    def begin(self, now: float) -> None:
        self._started_at = self._last_inbound = self._last_sent = now

    def feed(self, line: str, now: float) -> None:
        if self._phase is _Phase.CLOSED:
            return
        self._last_inbound = now
        try:
            message = _parse(line)
            self._dispatch(message, now)
        except LinkError as failure:
            self._close(failure)

    def tick(self, now: float) -> None:
        if self._phase is _Phase.CLOSED:
            return
        timings = self._timings
        if self._phase is not _Phase.READY or timings is None:
            if now - self._started_at > self._handshake_timeout_s:
                self._close(
                    LinkLostError(
                        f"the bridge did not finish its greeting within {self._handshake_timeout_s:g} s"
                    )
                )
            return
        if now - self._last_inbound > timings.idle_watchdog_s:
            self._close(
                LinkLostError(
                    f"nothing came from the host for {now - self._last_inbound:.1f} s "
                    f"(its watchdog is {timings.idle_watchdog_s:g} s): the link is half open"
                )
            )
            return
        if now - self._last_sent >= timings.ping_every_s:
            try:
                self._write({"type": "ping"}, now)
            except LinkError as failure:
                self._close(failure)

    def call(self, method: str, params: dict[str, object], now: float) -> int:
        """Send a call; its id comes back in exactly one `on_result` or `on_call_error`.

        @raise LinkLostError the conversation is not ready, or is over."""
        if self._phase is not _Phase.READY:
            raise LinkLostError("the link is not up")
        self._next_id += 1
        call_id = self._next_id
        self._pending.add(call_id)
        try:
            self._write(
                {"type": "call", "id": call_id, "method": method, "params": params}, now
            )
        except LinkError as failure:
            self._close(failure)
            raise
        return call_id

    def close(self) -> None:
        """The desktop ends it."""
        self._close(None)

    def lost(self, reason: LinkLostError) -> None:
        """The transport says the pipe is gone."""
        self._close(reason)

    # -- the conversation -----------------------------------------------------------------

    def _dispatch(self, message: dict[str, object], now: float) -> None:
        kind = message.get("type")
        if self._phase is _Phase.AWAIT_HELLO:
            self._on_bridge_hello(kind, message, now)
        elif self._phase is _Phase.AWAIT_WELCOME:
            self._on_welcome(kind, message)
        elif kind == "pong":
            return
        elif kind == "result" or kind == "error":
            self._on_answer(kind, message)
        elif kind == "event":
            self._listener.on_event(message)
        elif kind == "refused":
            raise _refusal(message)
        else:
            logger.warning("[link-desk] a message of unknown type %r was ignored", kind)

    def _on_bridge_hello(
        self, kind: object, message: dict[str, object], now: float
    ) -> None:
        if kind == "refused":
            raise _refusal(message)
        if kind != "hello":
            raise BridgeRefusedError("no_hello", "the host did not greet first")
        body = {
            k: v for k, v in message.items() if k != "type" and k not in _TIMING_KEYS
        }
        try:
            host = Hello.from_wire(body)
        except WireDecodeError as failure:
            raise BridgeRefusedError("bad_hello", str(failure)) from failure
        refusal = judge(host, self._hello)
        if refusal is not None:
            logger.warning(
                "[link-desk] the host runs another build: %s",
                ", ".join(refusal.differs),
            )
            raise VersionDifferenceError(refusal.words)
        self._write({"type": "hello", **self._hello.to_wire()}, now)
        self._phase = _Phase.AWAIT_WELCOME

    def _on_welcome(self, kind: object, message: dict[str, object]) -> None:
        if kind == "refused":
            raise _refusal(message)
        if kind != "welcome":
            raise BridgeRefusedError(
                "no_welcome", "the host did not welcome this desktop"
            )
        self._timings = _timings_of(message)
        self._phase = _Phase.READY
        self._listener.on_ready(self._timings)

    def _on_answer(self, kind: object, message: dict[str, object]) -> None:
        call_id = message.get("id")
        if type(call_id) is not int or call_id not in self._pending:
            logger.warning(
                "[link-desk] an answer to no pending call (id %r) was ignored", call_id
            )
            return
        self._pending.discard(call_id)
        if kind == "result":
            data = message.get("data")
            self._listener.on_result(call_id, data if isinstance(data, dict) else {})
            return
        self._listener.on_call_error(
            call_id, str(message.get("code", "")), str(message.get("message", ""))
        )

    # -- output ---------------------------------------------------------------------------

    def _write(self, message: dict[str, object], now: float) -> None:
        self._last_sent = now
        self._send(message)

    def _close(self, reason: LinkError | None) -> None:
        if self._phase is _Phase.CLOSED:
            return
        self._phase = _Phase.CLOSED
        self._pending.clear()
        self._listener.on_closed(reason)


def _parse(line: str) -> dict[str, object]:
    try:
        document = json.loads(line)
    except (ValueError, RecursionError) as failure:
        raise BridgeRefusedError(
            "bad_json", "the host sent a line that is not JSON"
        ) from failure
    if type(document) is not dict:
        raise BridgeRefusedError(
            "bad_json", "the host sent a line that is not an object"
        )
    return document


def _timings_of(message: dict[str, object]) -> LinkTimings:
    heartbeat, watchdog = message.get("heartbeat_s"), message.get("idle_watchdog_s")
    for value in (heartbeat, watchdog):
        if type(value) not in (int, float) or value <= 0:  # type: ignore[operator]
            raise BridgeRefusedError(
                "bad_welcome", "the welcome names no usable heartbeat"
            )
    return LinkTimings(float(heartbeat), float(watchdog))  # type: ignore[arg-type]


def _refusal(message: dict[str, object]) -> LinkError:
    words = str(message.get("words", ""))[:300]
    reason = str(message.get("reason", ""))
    if reason == "incompatible":
        return VersionDifferenceError(words)
    return BridgeRefusedError(reason, words)
