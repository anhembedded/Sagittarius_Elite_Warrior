"""A host document as a file in its wire form, written by the host and read by the bridge (`EPIC-047H`).

@details The market-data and host-reads files are encoded by the link's own reflective codec
(`IWireCodec`, `EPIC-047A`) and not by hand as the host-facts file is: the bytes on disk are the message
the bridge puts on the wire, so there is one description of each file (the type) and a drift between a
hand encoding and a wire form is not possible. A field is added within a version (a default), never
renamed (`test_wire_names_are_pinned`).

`WireDocumentSink` is the host's side (atomic, owner-only, `owner_only_atomic_file`). `WireDocumentView`
is the bridge's: each `look` reads the whole file; a torn, unreadable or older one never replaces the
document held, and the age that matters is the host's own cadence (`LIVE_AFTER_HEARTBEATS` of its
`heartbeat_s`), exactly the rule `FileHostFactsView` states for the host-facts file.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.owner_only_atomic_file import (
    write_owner_only_atomically,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_watch import (
    LIVE_AFTER_HEARTBEATS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_document_sink import (
    IDocumentSink,
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
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_wire_codec import (
    IWireCodec,
    WireCodecError,
)


class WireDocumentSink[Document](IDocumentSink[Document]):
    def __init__(self, path: Path, codec: IWireCodec, root: str) -> None:
        self._path = path
        self._codec = codec
        self._root = root

    def publish(self, document: Document) -> None:
        message = self._codec.encode(self._root, document)
        write_owner_only_atomically(
            self._path, json.dumps(message, separators=(",", ":")).encode("utf-8")
        )


class WireDocumentView[Document](IBridgeFacts):
    def __init__(
        self,
        path: Path,
        codec: IWireCodec,
        root: str,
        header_of: Callable[[Document], HostFactsHeader],
        clock: IOperationsClock,
    ) -> None:
        self._path = path
        self._codec = codec
        self._root = root
        self._header_of = header_of
        self._clock = clock
        self._held: Document | None = None

    def look(self) -> FactsLook:
        problem = self._read()
        held = self._held
        if held is None:
            return FactsLook(FactsState.MISSING, problem=problem)
        header = self._header_of(held)
        age_s = (self._clock.now() - header.written_at).total_seconds()
        live = age_s <= LIVE_AFTER_HEARTBEATS * header.heartbeat_s
        return FactsLook(
            FactsState.LIVE if live else FactsState.STALE,
            revision=header.revision,
            age_s=age_s,
            document=Wired(self._root, held),
            problem=problem,
        )

    def _read(self) -> str:
        kept = ", the last good one is kept" if self._held else ""
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return f"there is no file{kept}"
        except OSError as failure:
            return f"the file cannot be read ({type(failure).__name__}){kept}"
        try:
            found = cast("Document", self._codec.decode(json.loads(raw)))
        except (ValueError, WireCodecError) as failure:
            return f"the file is unreadable{kept}: {type(failure).__name__}"
        held = self._held
        if held is not None and (
            self._header_of(found).revision < self._header_of(held).revision
        ):
            return "an older revision was ignored"
        self._held = found
        return ""
