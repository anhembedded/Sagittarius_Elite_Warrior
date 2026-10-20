"""`EPIC-026L` — where the day's ledger and a trip are kept: one small record in the state folder."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    LossCapRecord,
)


class LossCapRecordUnreadableError(Exception):
    """A record exists and this build cannot read it. The message names the file and the problem,
    never the content."""


class ILossCapStore(ABC):
    @abstractmethod
    def read(self) -> LossCapRecord | None:
        """The record, or `None` when none was ever written.

        @raise LossCapRecordUnreadableError A record exists and cannot be read.
        """

    @abstractmethod
    def write(self, record: LossCapRecord) -> None:
        """Replace the record, atomically: a reader sees the old one or the new one.

        @raise OSError The record could not be written.
        """
