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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    LinkError,
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
        """A welcomed link: take the snapshot, subscribe. A `LinkError` here ends this connection."""

    @abstractmethod
    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None: ...


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
    ) -> None:
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
                link, epoch, closed = self._connect()
            except LinkError as failure:
                delay = next(delays, None) if failure.retriable else None
                if delay is None:
                    self._publish(LinkState.FAILED, failure.words, attempt)
                    return
                self._publish(
                    LinkState.RECONNECTING, f"{failure.words}; trying again", attempt
                )
                if self._stopped.wait(delay):
                    return
                continue
            if cut_at is not None:
                logger.info(
                    "[link-reconnect] welcomed again %d ms after the cut, on attempt %d",
                    round((self._monotonic() - cut_at) * 1000),
                    attempt,
                )
            delays, attempt = self._profile.reconnect.delays(), 0
            if not self._serve(link, epoch, closed):
                return
            cut_at = self._monotonic()

    def _connect(self) -> tuple[DeskLink, ConnectionEpoch, threading.Event]:
        self._epochs += 1
        epoch = ConnectionEpoch(self._epochs, RevisionGate())
        closed = threading.Event()
        link = DeskLink(
            self._transports.create(self._profile.protocol),
            self._hello,
            on_event=lambda event: self._observer.on_event(epoch, event),
            on_closed=lambda _reason: closed.set(),
            wall_clock=self._wall_clock,
        )
        link.connect(self._profile)
        return link, epoch, closed

    def _serve(
        self, link: DeskLink, epoch: ConnectionEpoch, closed: threading.Event
    ) -> bool:
        """Hold the link until it is lost (`True`) or the supervisor is stopped (`False`)."""
        self._publish(
            LinkState.CONNECTED, f"connected to {self._profile.host}", 0, link
        )
        try:
            self._observer.on_link_up(link, epoch)
        except LinkError as failure:
            logger.warning(
                "[link-supervisor] the first reads failed: %s", failure.words
            )
            link.close()
        while not closed.wait(_WATCH_SLICE_S):
            if self._stopped.is_set():
                link.close()
                return False
        link.close()  # a lost link still holds its transport's loop and thread
        self._data_as_of = link.data_as_of or self._data_as_of
        return not self._stopped.is_set()

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
