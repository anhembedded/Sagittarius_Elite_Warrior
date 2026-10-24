"""`EPIC-034H` — the Run step's facts: what stands in a bot's way that is not its plan or its
account.

`RunFacts` is what the assessment judges; `BotRunFacts` is what the host knows of it. Published
here (`EPIC-048B`) so the screen and a remote backend hold the same read model the Start path
judges.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)


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


@dataclass(frozen=True, slots=True)
class BotRunFacts:
    """`EPIC-048B` — what only the host knows of a bot's Run step, as `GetBotRunFactsQuery`
    answers it: every fact of `RunFacts` but the budget, and the caps the budget is judged
    against.

    The budget depends on the parameters on screen, which change on every edit; carrying the caps
    instead of the verdict lets the screen re-judge an edit 150 ms after the last keystroke
    without asking the host again (`presenter_pacing.REJUDGE_MS`, DERISK R1 §1.5).
    """

    #: The Run step's host facts; `budget_problem` is always empty here.
    facts: RunFacts
    caps: OwnerBudgetCaps
