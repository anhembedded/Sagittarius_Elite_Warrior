"""`EPIC-047D` — keep one profile's link up: connect, notice a cut, reconnect on the profile's policy.

One thread, started by `start`, loops `connect → serve until lost → wait → connect`. It is the only
place that decides to try again, and it decides from the **type** of the failure: a refused key, a
wrong host key, a version difference never retry (they would be refused again, and hammering `sshd`
is how a host bans its owner); an unreachable host or a lost link retry on `ReconnectPolicy`, the
first retry at once.

Each connection is a new `DeskLink`, a new transport and a new `ConnectionEpoch` with a fresh
`RevisionGate` (047C: never keep a gate across a reconnect). The observer's `on_link_up` takes the
snapshot and subscribes; if it fails with a `LinkError` the connection counts as lost.

The time from the cut to the next welcome is logged as `[link-reconnect]` with its milliseconds: it
is the figure the epic measures on the owner's real link (target under 2 s, 1909 ms measured).
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    CallFailedError,
    CallTimedOutError,
    LinkError,
    LinkLostError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
    LinkStatus,
    disconnected_words,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_link import DeskLink
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import Hello
from Sagittarius_Elite_Warrior.src.support.wire.revision_gate import RevisionGate

logger = logging.getLogger("App.LinkDesk")

_WATCH_SLICE_S = 0.1
#: How long a link must stay up before its next failure counts as a first one. A link that fails
#: sooner is flapping, and the next try waits the policy's next delay instead of coming at once.
STABLE_AFTER_S = 5.0


@dataclass(frozen=True, slots=True)
class ConnectionEpoch:
    """What belongs to one connection and to no other: its number and its revision gate."""

    number: int
    gate: RevisionGate[object]


class ILinkObserver(ABC):
    """What the owner of a supervisor does with a link. Called on the supervisor's thread."""

    @abstractmethod
    def on_status(self, status: LinkStatus) -> None: ...

    @abstractmethod
    def on_link_up(self, link: DeskLink, epoch: ConnectionEpoch) -> None:
        """A welcomed link: take the snapshot, subscribe.

        A `LinkError`, a refused call (`CallFailedError`) or a read that times out
        (`CallTimedOutError`) ends this connection: a refusal for good, anything else as a lost link
        that is retried on the policy's delays."""

    @abstractmethod
    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None: ...


class _Closure:
    """Why one connection ended: the first reason given wins, and `event` is set with it."""

    def __init__(self) -> None:
        self.event = threading.Event()
        self.reason: LinkError | None = None

    def finish(self, reason: LinkError | None) -> None:
        if not self.event.is_set():
            self.reason = reason
            self.event.set()


class LinkSupervisor:
    def __init__(
        self,
        profile: LinkProfile,
        transports: TransportRegistry,
        own_hello: Hello,
        observer: ILinkObserver,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        stable_after_s: float = STABLE_AFTER_S,
    ) -> None:
        self._stable_after_s = stable_after_s
        self._profile = profile
        self._transports = transports
        self._hello = own_hello
        self._observer = observer
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        self._epochs = 0
        self._data_as_of: datetime | None = None
        self._status = LinkStatus(LinkState.IDLE, "not connected")

    @property
    def status(self) -> LinkStatus:
        return self._status

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="link-supervisor", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5.0)

    def join(self, timeout_s: float) -> bool:
        """Wait for the thread to end (a refusal, a give-up or `stop`); whether it has."""
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
        return self._thread is None or not self._thread.is_alive()

    # -- the loop -------------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._keep_up()
        except Exception:
            logger.exception(
                "[link-supervisor] the supervisor failed on an unforeseen error"
            )
            self._publish(
                LinkState.FAILED,
                "the link stopped on an unforeseen error; the log says why",
            )

    def _keep_up(self) -> None:
        delays = self._profile.reconnect.delays()
        cut_at: float | None = None
        attempt = 0
        while not self._stopped.is_set():
            attempt += 1
            again = cut_at is not None or attempt > 1
            self._publish(
                LinkState.RECONNECTING if again else LinkState.CONNECTING,
                self._connecting_words(again, attempt),
                attempt,
            )
            try:
                link, epoch, closure = self._connect()
            except LinkError as failure:
                if not self._wait_to_retry(failure, delays, attempt):
                    return
                continue
            if cut_at is not None:
                logger.info(
                    "[link-reconnect] welcomed again %d ms after the cut, on attempt %d",
                    round((self._monotonic() - cut_at) * 1000),
                    attempt,
                )
            welcomed_at, attempt = self._monotonic(), 0
            ended = self._serve(link, epoch, closure)
            if ended is None:
                return
            cut_at = self._monotonic()
            if cut_at - welcomed_at >= self._stable_after_s:
                delays = (
                    self._profile.reconnect.delays()
                )  # a link that held earns a fresh start
                if not ended.retriable:
                    self._publish(LinkState.FAILED, ended.words)
                    return
            elif not self._wait_to_retry(ended, delays, attempt):
                return

    def _wait_to_retry(
        self, failure: LinkError, delays: Iterator[float], attempt: int
    ) -> bool:
        """Say why and wait the policy's next delay; `False` when the loop should end (a failure no
        retry can change, a spent policy, or a stop)."""
        delay = next(delays, None) if failure.retriable else None
        if delay is None:
            self._publish(LinkState.FAILED, failure.words, attempt)
            return False
        self._publish(LinkState.RECONNECTING, f"{failure.words}; trying again", attempt)
        return not self._stopped.wait(delay)

    def _connect(self) -> tuple[DeskLink, ConnectionEpoch, _Closure]:
        self._epochs += 1
        epoch = ConnectionEpoch(self._epochs, RevisionGate())
        closure = _Closure()
        link = DeskLink(
            self._transports.create(self._profile.protocol),
            self._hello,
            on_event=lambda event: self._observer.on_event(epoch, event),
            on_closed=closure.finish,
            wall_clock=self._wall_clock,
        )
        link.connect(self._profile)
        return link, epoch, closure

    def _serve(
        self, link: DeskLink, epoch: ConnectionEpoch, closure: _Closure
    ) -> LinkError | None:
        """Hold the link until it ends; why it ended (a link the desktop closed itself is a
        `LinkLostError`), or `None` when the supervisor is stopped."""
        self._publish(
            LinkState.CONNECTED, f"connected to {self._profile.host}", 0, link
        )
        try:
            self._observer.on_link_up(link, epoch)
        except (LinkError, CallFailedError, CallTimedOutError) as failure:
            # The first reads failed: a lost link, retried on the policy; a refusal is not.
            logger.warning("[link-supervisor] the first reads failed: %s", failure)
            closure.finish(
                failure
                if isinstance(failure, LinkError)
                else LinkLostError(f"the first reads failed ({failure})")
            )
            link.close()
        except Exception:
            link.close()  # the supervisor's last resort logs it; the link must not outlive it
            raise
        try:
            while not closure.event.wait(_WATCH_SLICE_S):
                if self._stopped.is_set():
                    return None
        finally:
            link.close()  # a lost link still holds its transport's loop and thread
        self._data_as_of = link.data_as_of or self._data_as_of
        if self._stopped.is_set():
            return None
        return closure.reason or LinkLostError("the link was closed")

    # -- status ---------------------------------------------------------------------------

    def _connecting_words(self, again: bool, attempt: int) -> str:
        if not again:
            return f"connecting to {self._profile.host}"
        return (
            f"{disconnected_words(self._data_as_of)}; reconnecting (attempt {attempt})"
        )

    def _publish(
        self,
        state: LinkState,
        words: str,
        attempt: int = 0,
        link: DeskLink | None = None,
    ) -> None:
        as_of = (link.data_as_of if link is not None else None) or self._data_as_of
        self._status = LinkStatus(state, words, as_of, attempt)
        self._observer.on_status(self._status)
