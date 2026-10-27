"""`EPIC-047H` — port: the planner inputs, fills and symbol rules the host last read for each bot.

@details The twin of `ILatestVenueReads` for the reads `BotReadRefresh` makes. A memory of reads that
happened, written only by a read that succeeded: a failed refresh leaves the last good read and its
`read_at` in place (decision record 2026-10-27, D4). Asking it costs the exchange nothing.

@par Extension cases
  · an age limit on what is carried - one filter in `latest()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    BotFillsRead,
    BotPlannerRead,
    HostExchangeReads,
    SymbolRulesRead,
)


class ILatestExchangeReads(ABC):
    @abstractmethod
    def record_planner(self, read: BotPlannerRead) -> None:
        """Replace the bot's planner read. Never raises."""

    @abstractmethod
    def record_fills(self, read: BotFillsRead) -> None:
        """Replace the bot's fills read. Never raises."""

    @abstractmethod
    def record_rules(self, read: SymbolRulesRead) -> None:
        """Replace the venue's and symbol's rules. Never raises."""

    @abstractmethod
    def retain(self, bot_ids: Collection[str]) -> None:
        """Forget the planner and fills of every bot not in `bot_ids` (a bot that was deleted)."""

    @abstractmethod
    def latest(self) -> HostExchangeReads:
        """Everything held, ordered by bot id (symbol rules by venue and symbol)."""
