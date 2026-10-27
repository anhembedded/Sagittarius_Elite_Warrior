"""`EPIC-047H` — port: where a published document goes (the file the bridge reads)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IDocumentSink[Document](ABC):
    @abstractmethod
    def publish(self, document: Document) -> None:
        """Make `document` the whole content of the file, or change nothing. @throws OSError"""
