"""The host-facts file as the bridge shows it: the last good document, and whether the host lives (`EPIC-047C`).

Each `look` reads the whole file. A torn, unreadable or older one never replaces the document held
(the host's writes are atomic, so torn means damaged, and `revision` only grows across restarts,
`first_revision_after`), exactly the rule `HostFactsWatch` states for the header; this keeps the
document, not only the header, because the desktop needs the facts. Liveness is the host's own
cadence: it rewrites at least every `heartbeat_s`, and is called quiet after
`LIVE_AFTER_HEARTBEATS` of them.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_watch import (
    LIVE_AFTER_HEARTBEATS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_codec import (
    IHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsLook,
    FactsState,
    Wired,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_facts import (
    IBridgeFacts,
)


class FileHostFactsView(IBridgeFacts):
    def __init__(
        self,
        path: Path,
        codec: IHostFactsCodec,
        clock: IOperationsClock,
        root: str,
    ) -> None:
        self._path = path
        self._codec = codec
        self._clock = clock
        self._root = root
        self._held: HostFactsDocument | None = None

    def look(self) -> FactsLook:
        problem = self._read()
        held = self._held
        if held is None:
            return FactsLook(FactsState.MISSING, problem=problem)
        age_s = (self._clock.now() - held.header.written_at).total_seconds()
        live = age_s <= LIVE_AFTER_HEARTBEATS * held.header.heartbeat_s
        return FactsLook(
            FactsState.LIVE if live else FactsState.STALE,
            revision=held.header.revision,
            age_s=age_s,
            document=Wired(self._root, held),
            problem=problem,
        )

    def _read(self) -> str:
        kept = ", the last good one is kept" if self._held else ""
        try:
            found = self._codec.decode(self._path.read_bytes())
        except FileNotFoundError:
            return f"there is no file{kept}"
        except OSError as failure:
            return f"the file cannot be read ({type(failure).__name__}){kept}"
        except HostFactsUnreadableError as failure:
            return f"the file is unreadable{kept}: {failure}"
        held = self._held
        if held is not None and found.header.revision < held.header.revision:
            return f"an older revision ({found.header.revision} < {held.header.revision}) was ignored"
        self._held = found
        return ""
