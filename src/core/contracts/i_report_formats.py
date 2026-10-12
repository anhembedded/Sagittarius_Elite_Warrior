"""The renderers a command may choose from, by name.

`EPIC-038B`. This is the lookup half only: a command asks for the renderer the
operator named and cannot add one. Adding is the composition root's job (the
class that implements this port also has `register`), so a command depends on
the narrow role it needs (Interface Segregation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.i_report_renderer import (
    IReportRenderer,
)


class IReportFormats(ABC):
    @abstractmethod
    def names(self) -> tuple[str, ...]:
        """Every registered format name, in registration order."""

    @abstractmethod
    def get(self, name: str) -> IReportRenderer | None:
        """The renderer registered under `name`, or `None` if there is none."""
