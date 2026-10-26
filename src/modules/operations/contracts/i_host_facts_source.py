"""Where the host's published facts are read from (`EPIC-047B`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
)


class IHostFactsSource(ABC):
    @abstractmethod
    def read_header(self) -> HostFactsHeader | None:
        """The file's header, or `None` when there is no file.
        @raise HostFactsUnreadableError The file is there and cannot be trusted."""
