"""`BOT-209` — the one thing the Plan says about where the bot stands, as a sentence.

Pure, so each state is tested without a widget. What was three texts in three places (the state
line with the run's note, "Start: 1 thing left" with the steps, and the blocking reason at the foot
of the editor) is one: the most important state first, in a sentence that names what to do, and
the lines that belong to it after it. The count of things left stays in the property table's
Readiness rows; here the first thing left is told in full and the others are counted.

Severity is the platform's message icon and, for a screen reader, its words (`NoticeBar`); colour
is never the signal.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.readiness_words import (
    CONNECTING,
    FieldLabelOf,
    item_sentence,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import NoticeKind

READY = "Ready to start"
#: States of a bot that has a run in which the owner has something to act on.
_NEEDS_THE_OWNER = frozenset(
    {
        BotLifecycleState.HALTED,
        BotLifecycleState.AWAITING_RECOVERY,
        BotLifecycleState.RECOVERING,
        BotLifecycleState.ERROR,
    }
)


@dataclass(frozen=True, slots=True)
class PlanStatus:
    """What the banner shows; `kind` `None` means it shows nothing."""

    kind: NoticeKind | None = None
    text: str = ""
    #: `None`: the tone of the kind's severity. "Ready to start" is good news and says so.
    tone: Tone | None = None


@dataclass(frozen=True, slots=True)
class StatusInputs:
    state: BotLifecycleState
    #: What the run said about the state (`BotFacts.note`).
    note: str
    #: `None` for a bot that has a run: its Start is not a next step.
    readiness: BotReadiness | None
    readiness_state: ReadinessState
    label_of: FieldLabelOf


def plan_status(inputs: StatusInputs) -> PlanStatus:
    readiness = inputs.readiness
    if readiness is None:
        return _of_a_run(inputs)
    if inputs.readiness_state is ReadinessState.CONNECTING:
        return PlanStatus(NoticeKind.INFORMATION, _with_extras(CONNECTING, inputs))
    if readiness.items:
        return PlanStatus(
            _blocked_kind(inputs.readiness_state),
            _with_extras(_first_left(inputs), inputs),
        )
    return PlanStatus(
        NoticeKind.INFORMATION, _with_extras(READY, inputs), Tone.POSITIVE
    )


def _blocked_kind(state: ReadinessState) -> NoticeKind:
    """A bot not connected waits for its account (the connection's own bar tells how to mend it);
    anything else left blocks Start."""
    if state in (ReadinessState.NOT_CONNECTED, ReadinessState.FAILED):
        return NoticeKind.WARNING
    return NoticeKind.CRITICAL


def _first_left(inputs: StatusInputs) -> str:
    readiness = inputs.readiness
    if readiness is None:
        return ""
    first, *others = readiness.items
    more = f" (and {len(others)} more before Start)" if others else ""
    return item_sentence(first, inputs.label_of) + more


def _with_extras(primary: str, inputs: StatusInputs) -> str:
    """The advisories the exchange gave and, for a bot that failed before, how it ended: each on
    its own line under the sentence, so the sentence stays the one thing to read first."""
    readiness = inputs.readiness
    lines = [primary]
    if readiness is not None:
        lines.extend(f"Note: {advisory.text}" for advisory in readiness.advisories)
    if inputs.note:
        lines.append(f"Last run: {inputs.note}")
    return "\n".join(lines)


def _of_a_run(inputs: StatusInputs) -> PlanStatus:
    if not inputs.note:
        return PlanStatus()
    kind = (
        NoticeKind.WARNING
        if inputs.state in _NEEDS_THE_OWNER
        else NoticeKind.INFORMATION
    )
    return PlanStatus(kind, inputs.note)
