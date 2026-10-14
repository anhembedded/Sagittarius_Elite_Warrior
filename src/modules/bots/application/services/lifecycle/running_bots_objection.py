"""`EPIC-029F` (ADR O4) — closing the app while a bot runs asks first."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

#: The states in which a bot has nothing on the exchange and nothing to watch.
_AT_REST = frozenset({BotLifecycleState.DRAFT, BotLifecycleState.STOPPED})


class RunningBotsObjection(ICloseObjection):
    """Names every bot that is not at rest, and what closing leaves behind.

    @details Every state but DRAFT and STOPPED counts: a PAUSED or HALTED bot
    still has a ladder or a base to look after, and a RECOVERING one has not
    yet been reconciled. Reads the store, which is local files, so it is
    cheap enough for the UI thread at close time.
    """

    def __init__(self, store: IBotStore) -> None:
        self._store = store

    def objection(self) -> str | None:
        active = [
            f"{stored.bot.definition.name} ({stored.bot.state.value})"
            for stored in self._store.load_all().bots
            if stored.bot.state not in _AT_REST
        ]
        if not active:
            return None
        return (
            f"Bots still active: {', '.join(active)}. Closing leaves their "
            "resting orders on the exchange, and nothing watches their stop "
            "loss or take profit until the app is open again."
        )
