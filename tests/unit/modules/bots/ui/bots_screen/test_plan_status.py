"""`BOT-209` — the one sentence the Plan dock says about where the bot stands."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessAdvisory,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status import (
    PlanStatus,
    StatusInputs,
    plan_status,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import NoticeKind

_HELD = (
    "ETHUSDT already holds a long position of 0.308 on Futures Testnet; a bot starts on a "
    "flat symbol, so close it first"
)


def _item(step: ReadinessStep, reason: str, fix: ReadinessFix = ReadinessFix.NONE):
    return ReadinessItem(step, "CODE", reason, fix, BotRefusal.VENUE_NOT_READY)


def _readiness(*items: ReadinessItem, notes: tuple[str, ...] = ()) -> BotReadiness:
    def step(which: ReadinessStep) -> StepReadiness:
        mine = tuple(i for i in items if i.step is which)
        return StepReadiness(which, StepStatus.OPEN if mine else StepStatus.DONE, mine)

    return BotReadiness(
        tuple(step(which) for which in ReadinessStep),
        tuple(ReadinessAdvisory("N", text) for text in notes),
    )


def _status(
    readiness: BotReadiness | None,
    state: ReadinessState = ReadinessState.RUN_BLOCKED,
    *,
    bot: S = S.DRAFT,
    note: str = "",
) -> PlanStatus:
    return plan_status(StatusInputs(bot, note, readiness, state, lambda _code: None))


def test_the_blocker_is_the_banner_with_the_stop_sign() -> None:
    status = _status(_readiness(_item(ReadinessStep.RUN, _HELD)))

    assert status.kind is NoticeKind.CRITICAL
    assert status.text == f"Run: {_HELD}"


def test_more_than_one_thing_left_tells_the_first_and_counts_the_rest() -> None:
    status = _status(
        _readiness(
            _item(ReadinessStep.RUN, "first"), _item(ReadinessStep.RUN, "second")
        )
    )

    assert status.text == "Run: first (and 1 more before Start)"


def test_where_to_fix_it_is_part_of_the_sentence() -> None:
    item = _item(ReadinessStep.RUN, "Stop it", ReadinessFix.RETRY_CONNECTION)

    assert _status(_readiness(item)).text.endswith("→ Bots → Retry venue account")


def test_a_failed_last_run_is_a_line_under_the_blocker_not_a_second_message() -> None:
    status = _status(
        _readiness(_item(ReadinessStep.RUN, _HELD)),
        note="L14 SELL: the request failed; see the log",
    )

    assert status.text.splitlines() == [
        f"Run: {_HELD}",
        "Last run: L14 SELL: the request failed; see the log",
    ]


def test_nothing_left_is_a_quiet_ready_line_and_the_exchanges_notes_follow_it() -> None:
    assert _status(_readiness(), ReadinessState.READY) == PlanStatus(
        NoticeKind.INFORMATION, "Ready to start"
    )
    noted = _status(
        _readiness(notes=("A previous run kept 0.1 ETH",)), ReadinessState.READY
    )

    assert noted.text.splitlines() == [
        "Ready to start",
        "Note: A previous run kept 0.1 ETH",
    ]


def test_connecting_and_not_connected_are_not_a_stop_sign() -> None:
    connecting = _status(_readiness(), ReadinessState.CONNECTING)
    waiting = _status(
        _readiness(_item(ReadinessStep.CONNECT, "Not connected: key refused")),
        ReadinessState.FAILED,
    )

    assert connecting == PlanStatus(NoticeKind.INFORMATION, "Connecting…")
    assert waiting.kind is NoticeKind.WARNING


def test_a_bot_with_a_run_says_how_it_ended_and_a_clean_one_says_nothing() -> None:
    halted = _status(None, bot=S.HALTED, note="leverage on the exchange is 5x")
    running = _status(None, bot=S.RUNNING, note="")

    assert halted == PlanStatus(NoticeKind.WARNING, "leverage on the exchange is 5x")
    assert running == PlanStatus()
    assert _status(None, bot=S.STOPPED, note="stopped by you").kind is (
        NoticeKind.INFORMATION
    )
