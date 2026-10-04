"""`EPIC-029F` — the kinds of bot this app can build, for the Bots tab.

The tab lists the kinds in the New Bot dialog and picks each bot's panel by
its `kind_id`; it never names a kind itself (ADR D2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind


class UnknownBotKindError(LookupError):
    """No kind of bot has this id."""


class IBotKindCatalog(ABC):
    @abstractmethod
    def kinds(self) -> tuple[IBotKind, ...]:
        """Every kind, in the order the New Bot dialog offers them."""

    @abstractmethod
    def kind(self, kind_id: str) -> IBotKind:
        """@raise UnknownBotKindError No kind has `kind_id`."""
