"""`EPIC-048B` — where a plan file is written, which is the machine the app runs on."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_file import (
    PlanFileRefused,
    PlanFileWritten,
)


class IPlanFileWriter(ABC):
    @abstractmethod
    def write_new(self, path: Path, text: str) -> PlanFileWritten | PlanFileRefused:
        """Write `text` to `path`, which must not exist: a plan is never written over another file."""
