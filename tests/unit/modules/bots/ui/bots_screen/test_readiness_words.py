"""`EPIC-034H` — what the Bots screen says about how far a bot is: pure words."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.readiness_words import (
    header,
    item_lines,
    next_fix,
    step_lines,
)


def _item(step: ReadinessStep, fix: ReadinessFix, target: str = "") -> ReadinessItem:
    return ReadinessItem(
        step,
        f"{step.name}_{fix.name}",
        "why",
        fix,
        BotRefusal.PARAMETERS_REFUSED,
        target,
    )


def _readiness(*items: ReadinessItem) -> BotReadiness:
    def step(kind: ReadinessStep) -> StepReadiness:
        mine = tuple(i for i in items if i.step is kind)
        return StepReadiness(kind, StepStatus.OPEN if mine else StepStatus.DONE, mine)

    return BotReadiness(tuple(step(kind) for kind in ReadinessStep))


def _label(code: str) -> str | None:
    return {"CAPITAL": "Capital (quote)"}.get(code)


def test_the_header_counts_and_says_ready_when_nothing_is_left() -> None:
    left = _readiness(_item(ReadinessStep.RUN, ReadinessFix.NONE))

    assert header(left, ReadinessState.RUN_BLOCKED) == "1 thing left"
    assert header(_readiness(), ReadinessState.READY) == "Ready to start"


def test_a_connecting_or_unselected_bot_is_said_by_its_state_not_by_its_count() -> None:
    left = _readiness(_item(ReadinessStep.CONNECT, ReadinessFix.WAIT))

    assert header(left, ReadinessState.CONNECTING) == "Connecting…"
    assert header(left, ReadinessState.NOT_CONNECTED) == "Not connected"


def test_each_step_is_numbered_and_names_what_it_waits_for() -> None:
    readiness = BotReadiness(
        (
            StepReadiness(
                ReadinessStep.CONNECT,
                StepStatus.OPEN,
                (_item(ReadinessStep.CONNECT, ReadinessFix.WAIT),),
            ),
            StepReadiness(ReadinessStep.DESIGN, StepStatus.WAITING),
            StepReadiness(ReadinessStep.RUN, StepStatus.WAITING),
        )
    )

    assert step_lines(readiness) == (
        "1. Connect: 1 thing left",
        "2. Design: waits for Connect",
        "3. Run: waits for Connect",
    )


def test_an_item_says_its_step_its_reason_and_where_to_fix_it() -> None:
    lines = item_lines(
        _readiness(
            _item(ReadinessStep.CONNECT, ReadinessFix.RETRY_CONNECTION),
            _item(ReadinessStep.DESIGN, ReadinessFix.EDIT_FIELD, "CAPITAL"),
            _item(ReadinessStep.DESIGN, ReadinessFix.EDIT_FIELD, "KEY"),
            _item(ReadinessStep.RUN, ReadinessFix.STOP_OTHER_BOT, "b00002"),
            _item(ReadinessStep.RUN, ReadinessFix.NONE),
        ),
        _label,
    )

    assert lines == (
        "• Connect: why → Bots → Retry venue account",
        "• Design: why → edit Capital (quote)",
        "• Design: why",
        "• Run: why → select that bot, then Bots → Stop…",
        "• Run: why",
    )


def test_the_next_fix_is_the_first_item_the_screen_can_do_something_about() -> None:
    readiness = _readiness(
        _item(ReadinessStep.CONNECT, ReadinessFix.WAIT),
        _item(ReadinessStep.DESIGN, ReadinessFix.EDIT_FIELD, "KEY"),
        _item(ReadinessStep.DESIGN, ReadinessFix.EDIT_FIELD, "CAPITAL"),
        _item(ReadinessStep.RUN, ReadinessFix.NONE),
    )

    found = next_fix(readiness, _label)

    assert found is not None
    assert found.target == "CAPITAL"


def test_there_is_no_next_fix_when_every_item_waits_or_has_none() -> None:
    readiness = _readiness(
        _item(ReadinessStep.CONNECT, ReadinessFix.WAIT),
        _item(ReadinessStep.RUN, ReadinessFix.NONE),
    )

    assert next_fix(readiness, _label) is None
    assert next_fix(_readiness(), _label) is None
