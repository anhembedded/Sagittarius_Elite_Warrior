"""`EPIC-034H` — what the Bots screen says about how far a bot is, in words.

Pure over a `BotReadiness`, so each sentence is tested without a widget. Every
state is said in words, never in colour alone (`ui-presentation-rule.md` §1):
a step is done, has N things left, or waits for the step before it; an item
says why and, when there is something to do, where.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)

#: A kind's editor says which field a design item is about, or `None` when it
#: is about none of its fields (the key's permission).
type FieldLabelOf = Callable[[str], str | None]

CONNECTING = "Connecting…"
NOT_CONNECTED = "Not connected"
RETRY_WORDS = "Bots → Retry venue account"
STOP_WORDS = "select that bot, then Bots → Stop…"


def header(readiness: BotReadiness, state: ReadinessState) -> str:
    """The count, or where the bot stands when nothing is left to count."""
    if state is ReadinessState.CONNECTING:
        return CONNECTING
    if state is ReadinessState.NOT_CONNECTED:
        return NOT_CONNECTED
    return readiness.summary


def step_lines(readiness: BotReadiness) -> tuple[str, ...]:
    """One line per step, numbered, naming what each waits for."""
    lines: list[str] = []
    open_before = ""
    for number, step in enumerate(readiness.steps, start=1):
        lines.append(f"{number}. {step.step.value}: {_step_words(step, open_before)}")
        if step.status is StepStatus.OPEN and not open_before:
            open_before = step.step.value
    return tuple(lines)


def _step_words(step: StepReadiness, open_before: str) -> str:
    if step.status is StepStatus.DONE:
        return "done"
    if step.status is StepStatus.WAITING:
        return f"waits for {open_before}" if open_before else "nothing to do yet"
    count = len(step.items)
    return f"{count} thing{'' if count == 1 else 's'} left"


def item_lines(readiness: BotReadiness, label_of: FieldLabelOf) -> tuple[str, ...]:
    return tuple(_item_line(item, label_of) for item in readiness.items)


def _item_line(item: ReadinessItem, label_of: FieldLabelOf) -> str:
    fix = _fix_words(item, label_of)
    return f"• {item.step.value}: {item.reason}" + (f" → {fix}" if fix else "")


def _fix_words(item: ReadinessItem, label_of: FieldLabelOf) -> str:
    if item.fix is ReadinessFix.RETRY_CONNECTION:
        return RETRY_WORDS
    if item.fix is ReadinessFix.STOP_OTHER_BOT:
        return STOP_WORDS
    if item.fix is ReadinessFix.EDIT_FIELD:
        label = label_of(item.target)
        return f"edit {label}" if label else ""
    return ""


def next_fix(readiness: BotReadiness, label_of: FieldLabelOf) -> ReadinessItem | None:
    """The first item whose fix is something the screen can do."""
    for item in readiness.items:
        if item.fix in (ReadinessFix.RETRY_CONNECTION, ReadinessFix.STOP_OTHER_BOT):
            return item
        if item.fix is ReadinessFix.EDIT_FIELD and label_of(item.target):
            return item
    return None
