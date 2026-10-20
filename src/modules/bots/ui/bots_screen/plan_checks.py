"""`BOT-209` — what the kind says about a plan, as a list of checks instead of a wall of text.

Pure over `Verdict`s, so each rule is tested without a widget. A check is one verdict with its
words split by how much room a place has: the `title` (a noun phrase the kind names at its
source), the `headline` (one line, rounded for reading) and the `detail` (the whole sentence with
the numbers behind it, exactly what `verdict_line` always said). Those that need a person's
attention (a refusal, then a warning) come first; every check that passed is counted, never
listed, until the person opens the count.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_judge import (
    verdict_line,
)

#: The order attention is asked in: what blocks Start, then what is only advised.
_ATTENTION_ORDER = (VerdictSeverity.REFUSED, VerdictSeverity.WARNING)


@dataclass(frozen=True, slots=True)
class PlanCheck:
    """One verdict, in the three sizes the Plan dock needs."""

    code: str
    title: str
    severity: VerdictSeverity
    #: One line: the verdict's own `summary`, else its `reason` (already one sentence).
    headline: str
    #: The whole sentence and its numbers, as the verdict list always wrote it.
    detail: str

    @property
    def needs_attention(self) -> bool:
        return self.severity is not VerdictSeverity.OK

    @property
    def blocks(self) -> bool:
        return self.severity is VerdictSeverity.REFUSED


@dataclass(frozen=True, slots=True)
class PlanChecks:
    """Every check of a plan: the ones that need attention first, the passed ones after."""

    attention: tuple[PlanCheck, ...] = ()
    passed: tuple[PlanCheck, ...] = ()

    @property
    def everything(self) -> tuple[PlanCheck, ...]:
        return (*self.attention, *self.passed)

    @property
    def blocking(self) -> int:
        return sum(check.blocks for check in self.attention)

    @property
    def warnings(self) -> int:
        return len(self.attention) - self.blocking

    @property
    def passed_text(self) -> str:
        """The one row the passed checks fold into."""
        count = len(self.passed)
        return f"{count} check{'' if count == 1 else 's'} passed"

    @property
    def tally(self) -> str:
        """How the plan stands, in words, for the list's heading."""
        if not self.everything:
            return ""
        parts = []
        if self.blocking:
            parts.append(f"{self.blocking} blocking Start")
        if self.warnings:
            parts.append(f"{self.warnings} warning{'' if self.warnings == 1 else 's'}")
        return ", ".join(parts) if parts else "all passed"

    def check_for(self, code: str) -> PlanCheck | None:
        """The first check with `code`, a field's hint reading what the list shows."""
        return next((c for c in self.everything if c.code == code), None)


def plan_checks_of(verdicts: tuple[Verdict, ...]) -> PlanChecks:
    """@param verdicts what the kind answered, in its own order; the order is kept within a severity."""
    checks = tuple(_check_of(verdict) for verdict in verdicts)
    attention = tuple(
        check
        for severity in _ATTENTION_ORDER
        for check in checks
        if check.severity is severity
    )
    passed = tuple(check for check in checks if not check.needs_attention)
    return PlanChecks(attention, passed)


def _check_of(verdict: Verdict) -> PlanCheck:
    return PlanCheck(
        code=verdict.code,
        title=_title_of(verdict),
        severity=verdict.severity,
        headline=verdict.summary or verdict.reason,
        detail=verdict_line(verdict),
    )


def _title_of(verdict: Verdict) -> str:
    title = verdict.title or verdict.code.replace("_", " ").capitalize()
    return f"{title} ({verdict.subject})" if verdict.subject else title
