"""`EPIC-026L` — the owner's acknowledgement of a tripped account-level loss cap."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum


class LossCapAcknowledgement(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    NOT_TRIPPED = "not_tripped"
    #: The day's loss is still at or above the figure: clearing the trip would only trip it again.
    STILL_AT_FIGURE = "still_at_figure"


class ILossCapAcknowledgement(ABC):
    @abstractmethod
    def acknowledge(self) -> LossCapAcknowledgement:
        """Clear a tripped cap so bots may start again. The day's count is **not** reset: it keeps
        adding up from 00:00 UTC, so the cap trips again at the figure unless the owner has
        raised it. Refused while the day's loss is at or above the figure. Starts and resumes
        no bot."""
