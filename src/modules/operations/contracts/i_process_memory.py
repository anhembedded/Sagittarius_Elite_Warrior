"""How much memory this process holds (`EPIC-038D`).

The health line carries the resident size because an outage-driven blow-up is the
documented failure of a long-running bot host (`RESEARCH` R8): a feed that
reconnects without letting go of the last one grows by the hour, and a person
reading the line sees it before the machine does. Where the platform gives no
answer the reading is `None`, which the line spells `na`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IProcessMemory(ABC):
    @abstractmethod
    def resident_mb(self) -> int | None:
        """Resident memory in whole megabytes, or `None` if it cannot be read."""
