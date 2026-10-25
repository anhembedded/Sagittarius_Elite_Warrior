"""`EPIC-048B` — what the assessment of one bot answers: the judgement a screen shows."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


@dataclass(frozen=True, slots=True)
class BotAssessment:
    #: What is left before Start, for a bot at rest; `None` for one that already has a run,
    #: whose Start is not a next step.
    readiness: BotReadiness | None
    #: What the exchange's facts leave in a HALTED bot's Resume's way, in the words the Resume
    #: use case refuses with (`BOT-174`); empty when nothing does, or the bot proposes no Resume.
    resume_blocked_by: str = ""
    #: The readiness items that are about a parameter, as the verdicts the kind's editor shows
    #: beside that field (`CAPITAL_ABOVE_BALANCE` on the Capital field).
    field_verdicts: tuple[Verdict, ...] = ()
