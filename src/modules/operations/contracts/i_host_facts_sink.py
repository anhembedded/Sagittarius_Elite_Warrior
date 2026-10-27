"""Where the host's facts go (`EPIC-047B`).

@par Extension cases
  · a second destination (a Prometheus textfile) - one more implementation handed to the publisher.
"""

from __future__ import annotations

from abc import abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_document_sink import (
    IDocumentSink,
)


class IHostFactsSink(IDocumentSink[HostFactsDocument]):
    @abstractmethod
    def publish(self, document: HostFactsDocument) -> None:
        """Make `document` the current file. Atomic: a reader sees the previous file or this
        one, never half of either.
        @raise OSError The file could not be written."""
