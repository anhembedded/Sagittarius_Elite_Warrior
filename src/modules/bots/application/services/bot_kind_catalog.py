"""`EPIC-029F` — the registered kinds of bot, by id."""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)


class BotKindCatalog(IBotKindCatalog):
    def __init__(self, kinds: Sequence[IBotKind]) -> None:
        self._kinds = tuple(kinds)
        ids = [kind.kind_id for kind in self._kinds]
        if len(set(ids)) != len(ids):
            raise ValueError(f"two kinds share an id: {ids}")

    def kinds(self) -> tuple[IBotKind, ...]:
        return self._kinds

    def kind(self, kind_id: str) -> IBotKind:
        for candidate in self._kinds:
            if candidate.kind_id == kind_id:
                return candidate
        raise UnknownBotKindError(f"no kind of bot is called {kind_id!r}")
