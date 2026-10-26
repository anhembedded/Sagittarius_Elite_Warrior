"""The host-facts file's encoding, behind one seam (`EPIC-047B`).

@par Extension cases
  · `EPIC-047A`'s reflective codec - one more implementation; the file's shape (`HostFactsDocument`)
    and the writer do not change;
  · decoding the facts body - added to this port by the child that reads it (`EPIC-047C`); the
    header is all the writer's own side needs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
    HostFactsHeader,
)


class IHostFactsCodec(ABC):
    @abstractmethod
    def encode(self, document: HostFactsDocument) -> bytes:
        """The file's bytes. Holds only the fields of the document's types."""

    @abstractmethod
    def decode_header(self, raw: bytes) -> HostFactsHeader:
        """@raise HostFactsUnreadableError Not a host-facts file of this schema."""
