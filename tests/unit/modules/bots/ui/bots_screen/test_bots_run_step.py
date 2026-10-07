"""`EPIC-034H` — the Run step on the real presenter: the three steps in order,
every item left with its reason and its fix before the click, one command that
does the first fix, and Save and start as the primary action.

The numbers are the Connect step's read and the planner's; the words are the
readiness query's; nothing here is asserted from a double of the assessment.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    FIX_NEXT,
    RETRY_CONNECTION,
    lifecycle_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)

from .bots_screen_fixtures import NOW, SYMBOL, stored
from .connect_screen_helpers import failure, fresh_snapshot, select, start_rule


def _plan(screen):
    return screen.view.plan


def _steps(screen) -> list[str]:
    return _plan(screen).readiness_steps.text().splitlines()


def _fix(screen):
    return screen.actions.action(FIX_NEXT)


def test_a_new_bot_walks_connect_design_run_and_ends_ready(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    select(screen, "a00001")

    assert _plan(screen).readiness_header.text() == "Start: Connecting…"
    assert _steps(screen)[0] == "1. Connect: 1 thing left"
    assert screen.presenter._account.state is ReadinessState.CONNECTING

    screen.settle()

    assert _plan(screen).readiness_header.text() == "Start: Ready to start"
    assert _steps(screen) == [
        "1. Connect: done",
        "2. Design: done",
        "3. Run: done",
    ]
    assert screen.presenter._account.state is ReadinessState.READY
    assert start_rule(screen)[0]
    assert _plan(screen).readiness_items.isHidden()


def test_start_is_the_one_primary_action_and_is_worded_save_and_start(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    command = screen.actions.action(lifecycle_id(BotAction.START))

    assert command.text().replace("&", "") == "Save and start"
    assert command.isEnabled()
    assert "Save the changed parameters" in command.toolTip()


def test_start_is_disabled_with_the_count_and_the_tip_says_what_is_left(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), available=Decimal(800)))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    command = screen.actions.action(lifecycle_id(BotAction.START))

    assert not command.isEnabled()
    assert _plan(screen).readiness_header.text() == "Start: 1 thing left"
    assert "1 thing left: The capital is 1000 USDT" in command.toolTip()
    assert screen.presenter._account.state is ReadinessState.DESIGNING
    assert [s.status for s in screen.view.model.readiness.steps] == [
        StepStatus.DONE,
        StepStatus.OPEN,
        StepStatus.WAITING,
    ]


def test_an_item_names_its_reason_and_where_to_fix_it(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), available=Decimal(800)))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    line = _plan(screen).readiness_items.text()

    assert "Design: The capital is 1000 USDT, above the 800.00 USDT available" in line
    assert line.endswith("→ edit Capital (quote)")


def test_fix_next_brings_the_field_a_design_item_is_about_forward(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(replace(fresh_snapshot(), available=Decimal(800)))
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    screen.view.show()
    qtbot.waitExposed(screen.view)
    screen.view.activateWindow()
    assert _fix(screen).isEnabled()

    _fix(screen).trigger()

    panel = screen.view._kind_panel
    assert panel is not None
    qtbot.waitUntil(panel.capital.hasFocus)


def test_fix_next_after_the_fix_is_off_because_nothing_is_left(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert not _fix(screen).isEnabled()


def test_a_failed_read_is_a_connect_item_whose_fix_reads_again(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(failure(ConnectionFailureKind.MAINTENANCE))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert _steps(screen)[0] == "1. Connect: 1 thing left"
    assert _steps(screen)[1] == "2. Design: waits for Connect"
    assert "under maintenance" in _plan(screen).readiness_items.text()
    assert "Bots → Retry venue account" in _plan(screen).readiness_items.text()
    assert screen.presenter._account.state is ReadinessState.FAILED

    screen.account.answer_with(replace(fresh_snapshot(), read_at=NOW))
    _fix(screen).trigger()
    screen.settle()

    assert len(screen.account.symbols_read) == 2
    assert _plan(screen).readiness_header.text() == "Start: Ready to start"
    assert screen.actions.action(RETRY_CONNECTION).isEnabled() is False


def test_another_active_bot_is_an_item_and_fix_next_selects_it(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("b00002", S.RUNNING)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert "Bot b00002 is still active; stop it before starting another" in (
        _plan(screen).readiness_items.text()
    )
    assert "select that bot, then Bots → Stop…" in _plan(screen).readiness_items.text()
    assert not start_rule(screen)[0]
    assert screen.presenter._account.state is ReadinessState.RUN_BLOCKED

    _fix(screen).trigger()
    screen.settle()

    assert screen.view.model.selected is not None
    assert screen.view.model.selected.bot_id == "b00002"


def test_a_symbol_held_by_another_owner_is_an_item_with_no_fix_on_screen(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.trading_session.claim_symbol(SYMBOL, "strategy.1")
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    assert f"{SYMBOL} is held by another owner" in _plan(screen).readiness_items.text()
    assert not start_rule(screen)[0]
    assert not _fix(screen).isEnabled()


def test_a_bot_with_a_run_shows_no_progress_and_a_stopped_bot_does(
    open_bots_screen,
) -> None:
    screen = open_bots_screen(
        [stored("a00001", S.RUNNING), stored("b00002", S.STOPPED)]
    )
    screen.settle()

    select(screen, "a00001")
    screen.settle()
    assert _plan(screen).readiness_header.isHidden()

    select(screen, "b00002")
    screen.settle()
    assert not _plan(screen).readiness_header.isHidden()


def test_a_click_refused_after_the_screen_said_ready_reads_in_the_screens_words(
    open_bots_screen,
) -> None:
    """The race the handler reports: the screen was ready, then another bot
    took the exchange before the click. The refusal is the readiness's own."""
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("b00002", S.DRAFT)])
    screen.settle()
    select(screen, "a00001")
    screen.settle()
    assert start_rule(screen)[0]
    screen.store.save(stored("b00002", S.RUNNING))

    screen.view.model.action_requested.emit(BotAction.START.value)
    screen.settle()

    status = screen.view.model.statusMessage
    assert "1 thing left: Bot b00002 is still active" in status
