"""`EPIC-047E` — the host's published picture, kept up to date from the link.

@details A `LinkSupervisor` calls this `ILinkObserver` on its own thread: at each welcome (`on_link_up`) it takes the
bridge's snapshot and subscribes, afterwards `on_event` applies what changed. The screen reads it through
`IHostWorld.current()` from any thread and gets an immutable `HostWorld`, so no reader ever sees a half-applied
event.

@par Rules the picture keeps
  · a bot is applied only when its revision is greater than the one held (`RevisionGate`), so a snapshot that was
    overtaken by an event cannot bring an older bot back; the gate is the connection's own (`ConnectionEpoch`),
    and an event from an older connection is ignored;
  · what the snapshot says is the whole truth at that moment: a bot, a file or a deletion the desktop missed
    while the link was down is corrected by it, never merged with the old picture;
  · the last picture stays when the link drops — `current()` then says `connected=False` and the time the desktop
    last heard from the host (decision record 2026-10-27, D5).

@par Extension cases
  · another host file — one more entry in `FILE_KINDS` and the field of `HostWorld` it feeds;
  · a screen that wants to hear a change — one more `IHostWorldListener`.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import (
    HostFile,
    HostFileState,
    HostWorld,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    RefusedBotFile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_world import IHostWorld
from Sagittarius_Elite_Warrior.src.modules.bots.link import decoded_bot_list
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_reads_document import (
    HostReadsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    MarketDataDocument,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.document_look import (
    NO_DOCUMENT,
    DocumentLook,
    look_of,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsState,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
    LinkStatus,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_link import DeskLink
from Sagittarius_Elite_Warrior.src.support.wire.desk.link_supervisor import (
    ConnectionEpoch,
    ILinkObserver,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

logger = logging.getLogger("App.VpsTab")

FACTS: Final = "facts"
MARKET: Final = "market"
READS: Final = "reads"
#: The host files the picture follows, by the kind the bridge names them.
FILE_KINDS: Final = (FACTS, MARKET, READS)


class IHostWorldListener(ABC):
    """Told, on the link's thread, what the last event changed. Must not block."""

    @abstractmethod
    def on_bot_changed(self, bot_id: str, removed: bool) -> None: ...

    @abstractmethod
    def on_market(self, market: MarketDataDocument) -> None: ...

    @abstractmethod
    def on_file_changed(self, kind: str) -> None:
        """A host file (`facts`, `market`, `reads`) moved or changed its liveness: the line above the tab and
        anything drawn from the file may need to be drawn again."""


class LinkHostWorld(ILinkObserver, IHostWorld):
    def __init__(
        self,
        roots: WireRoots,
        listener: IHostWorldListener | None = None,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._roots = roots
        self._listener = listener
        self._wall_clock = wall_clock
        self._lock = threading.RLock()
        self._bots: dict[str, BotSnapshot] = {}
        self._refused: dict[str, RefusedBotFile] = {}
        self._looks: dict[str, DocumentLook] = {
            kind: NO_DOCUMENT for kind in FILE_KINDS
        }
        self._looked_at: dict[str, datetime | None] = dict.fromkeys(FILE_KINDS)
        self._last_frame_at: datetime | None = None
        self._status = LinkStatus(LinkState.IDLE, "not connected")
        self._epoch_number = 0
        self._link: DeskLink | None = None
        self._world = HostWorld()

    # -- IHostWorld -----------------------------------------------------------------------

    def current(self) -> HostWorld:
        return self._world

    # -- what the rest of the shell reads --------------------------------------------------

    @property
    def status(self) -> LinkStatus:
        return self._status

    def look_at(self, kind: str) -> DocumentLook:
        """The latest look at one host file; `NO_DOCUMENT` before any."""
        with self._lock:
            return self._looks.get(kind, NO_DOCUMENT)

    def live_link(self) -> DeskLink | None:
        """The link of the current connection while it is up; `None` otherwise."""
        with self._lock:
            link = self._link
        return link if link is not None and link.is_up else None

    # -- ILinkObserver (the supervisor's thread) -------------------------------------------

    def on_status(self, status: LinkStatus) -> None:
        with self._lock:
            self._status = status
            if status.state is not LinkState.CONNECTED:
                self._link = None
            self._rebuild()

    def on_link_up(self, link: DeskLink, epoch: ConnectionEpoch) -> None:
        snapshot = link.call("snapshot")
        with self._lock:
            self._epoch_number = epoch.number
            self._link = link
            self._take_snapshot(snapshot, epoch)
        # Subscribing after the snapshot is safe: an event older than the snapshot is refused by the
        # revision gate, and the bridge numbers what it sends from the same counters.
        link.call("subscribe")
        logger.info(
            "[vps-world] epoch %d: %d bots, files %s",
            epoch.number,
            len(self._bots),
            {kind: look.state.value for kind, look in self._looks.items()},
        )

    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None:
        with self._lock:
            if epoch.number != self._epoch_number:
                return
            self._last_frame_at = self._wall_clock()
            kind = event.get("kind")
            if kind == "bot":
                self._take_bot_event(event, epoch)
            elif kind in FILE_KINDS and isinstance(kind, str):
                self._take_file(kind, event)
            self._rebuild()

    # -- applying -------------------------------------------------------------------------

    def _take_snapshot(
        self, snapshot: dict[str, object], epoch: ConnectionEpoch
    ) -> None:
        self._last_frame_at = self._wall_clock()
        listing = decoded_bot_list(self._roots.decode(snapshot["list"]))
        revisions = snapshot.get("revisions")
        self._bots = {}
        self._refused = {}
        if listing is not None:
            bots, refused = listing
            for bot in bots:
                revision = (
                    revisions.get(bot.bot_id, 0) if isinstance(revisions, dict) else 0
                )
                if epoch.gate.offer(bot.bot_id, int(revision), bot):
                    self._bots[bot.bot_id] = bot
            self._refused = {file.name: file for file in refused}
        documents = snapshot.get("documents")
        published = documents if isinstance(documents, dict) else {}
        self._take_file(FACTS, {"kind": FACTS, **_payload(snapshot.get("facts"))})
        # The snapshot is the whole truth: a file it does not carry is a file the host does not publish.
        for kind in (MARKET, READS):
            self._take_file(kind, {"kind": kind, **_payload(published.get(kind))})
        self._rebuild()

    def _take_bot_event(self, event: dict[str, object], epoch: ConnectionEpoch) -> None:
        bot_id = event.get("bot_id")
        revision = event.get("revision")
        if not isinstance(bot_id, str) or not isinstance(revision, int):
            return
        encoded = event.get("bot")
        bot = None if encoded is None else self._decode_bot(encoded)
        if not epoch.gate.offer(bot_id, revision, bot):
            return
        removed = bot is None
        if bot is None:
            self._bots.pop(bot_id, None)
            reason = event.get("refused")
            if isinstance(reason, str) and reason:
                self._refused[bot_id] = RefusedBotFile(bot_id, reason)
                removed = False
            else:
                self._refused.pop(bot_id, None)
        else:
            self._bots[bot_id] = bot
            self._refused.pop(bot_id, None)
        if self._listener is not None:
            self._listener.on_bot_changed(bot_id, removed)

    def _decode_bot(self, encoded: object) -> BotSnapshot | None:
        try:
            decoded = self._roots.decode(encoded)
        except WireDecodeError:
            logger.warning(
                "[vps-world] a bot of the host could not be read by this build"
            )
            return None
        return decoded if isinstance(decoded, BotSnapshot) else None

    def _take_file(self, kind: str, payload: dict[str, object]) -> None:
        look = look_of(self._roots, payload)
        self._looks[kind] = look
        self._looked_at[kind] = self._wall_clock()
        if self._listener is not None:
            self._listener.on_file_changed(kind)
        if (
            kind == MARKET
            and look.state is FactsState.LIVE
            and isinstance(look.document, MarketDataDocument)
            and self._listener is not None
        ):
            self._listener.on_market(look.document)

    def _rebuild(self) -> None:
        facts = self._looks[FACTS].document
        reads = self._looks[READS].document
        ordered = tuple(
            sorted(self._bots.values(), key=lambda bot: (bot.created_at, bot.bot_id))
        )
        self._world = HostWorld(
            bots=ordered,
            refused=tuple(self._refused.values()),
            held=facts.facts if isinstance(facts, HostFactsDocument) else None,
            held_file=self._file_of(FACTS),
            held_at=facts.header.written_at
            if isinstance(facts, HostFactsDocument)
            else None,
            reads=reads.reads if isinstance(reads, HostReadsDocument) else None,
            reads_file=self._file_of(READS),
            reads_at=reads.header.written_at
            if isinstance(reads, HostReadsDocument)
            else None,
            last_frame_at=self._last_frame_at,
            connected=self._status.state is LinkState.CONNECTED,
        )

    def _file_of(self, kind: str) -> HostFile:
        look = self._looks[kind]
        return HostFile(
            HostFileState(look.state.value), look.age_s, self._looked_at[kind]
        )


def _payload(raw: object) -> dict[str, object]:
    return raw if isinstance(raw, dict) else {}
