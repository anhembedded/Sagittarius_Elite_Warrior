"""The host-facts file's encoding, behind one seam (`EPIC-047B`).

@par Extension cases
  · `EPIC-047A`'s reflective codec - one more implementation; the file's shape (`HostFactsDocument`)
    and the writer do not change;
  · decoding the facts body - `decode`, added by the bridge (`EPIC-047C`) that reads the file;
    the writer's own side needs only the header.
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
    def decode(self, raw: bytes) -> HostFactsDocument:
        """The whole file: header and facts. Reads tolerantly: a key the types do not know is
        ignored, a missing one takes the field's default.
        @raise HostFactsUnreadableError Not a host-facts file of this schema, or malformed."""

    @abstractmethod
    def decode_header(self, raw: bytes) -> HostFactsHeader:
        """@raise HostFactsUnreadableError Not a host-facts file of this schema."""
