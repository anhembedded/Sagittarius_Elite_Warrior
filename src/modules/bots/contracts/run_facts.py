"""`EPIC-034H` — the Run step's facts: what stands in a bot's way that is not its plan or its
account.

`RunFacts` is what the assessment judges. Published here (`EPIC-048B`) so the screen and a remote
backend hold the same read model the Start path judges.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunFacts:
    """The Run step's facts; each is empty when it holds."""

    #: Why the venue cannot run a Spot Grid.
    venue_problem: str = ""
    #: The id of another bot on the same venue and symbol that is still active (ADR D20).
    other_active_bot: str = ""
    #: `EPIC-029J` J1b — the ids of the other active bots of the venue when they already number
    #: the venue's cap; empty while there is room.
    venue_full_of: tuple[str, ...] = ()
    #: `EPIC-029J` J1b (`EPIC-042E`) — the ids of the other bots of the venue that wait to
    #: recover: they are reconciled with the exchange only by their own Resume, so no other bot
    #: starts on the venue meanwhile (`other_active_bot.venue_recovering`, `BOT-201`).
    venue_recovering: tuple[str, ...] = ()
    #: Who else holds the symbol's lease.
    lease_holder: str = ""
    #: Which cap the owner budget exceeds.
    budget_problem: str = ""
