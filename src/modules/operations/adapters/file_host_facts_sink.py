"""`state/host-facts.json`, owner-only and atomic (`EPIC-047B`, decision G7a)."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.owner_only_atomic_file import (
    write_owner_only_atomically,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_codec import (
    IHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_sink import (
    IHostFactsSink,
)


class FileHostFactsSink(IHostFactsSink):
    def __init__(self, path: Path, codec: IHostFactsCodec) -> None:
        self._path = path
        self._codec = codec

    def publish(self, document: HostFactsDocument) -> None:
        write_owner_only_atomically(self._path, self._codec.encode(document))
