"""The time `status` and the snapshot publisher judge freshness by (`EPIC-038C`).

A port so a test says exactly what "now" is; `operations` keeps its own rather
than borrow another context's clock for a different purpose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class IOperationsClock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Now, timezone-aware, in UTC."""
