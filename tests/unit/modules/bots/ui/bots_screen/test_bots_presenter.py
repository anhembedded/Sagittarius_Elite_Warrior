"""`EPIC-029F` — the Bots screen over the bots module's real graph: the list,
the legal actions per state, the kind's verdicts, the dialogs, and the one
action at a time with its stale answers dropped."""

from __future__ import annotations

import threading

from PySide6.QtCore import QCoreApplication, QTimer
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    FIT_LEVELS,
    NEW_BOT,
    lifecycle_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_ui_fsm_matrix import (
    BotsUiState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard

from .bots_screen_fixtures import (
    GOOD_CONFIG,
    REFUSED_CONFIG,
    SYMBOL,
    VENUE,
    Answers,
    BotsScreen,
    stored,
)

S = BotLifecycleState


def _select(screen: BotsScreen, bot_id: str) -> None:
    screen.view.model.select_requested.emit(bot_id)
    screen.settle()


def _rule(screen: BotsScreen, action: BotAction) -> tuple[bool, str]:
    rule = screen.view.model.availability[action]
    return rule.enabled, rule.reason


def _mode(screen: BotsScreen) -> BotsUiState:
    assert screen.presenter.fsm is not None
    return screen.presenter.fsm.current_state


def test_the_list_names_every_stored_bot_and_its_state(open_bots_screen, qtbot) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT), stored("a00002", S.STOPPED)])
    screen.settle()

    rows = [
        (screen.view.bots.index(row, 0).data(), screen.view.bots.index(row, 4).data())
        for row in range(screen.view.bots.rowCount())
    ]
    assert sorted(rows) == [("grid a00001", "Draft"), ("grid a00002", "Stopped")]


def test_a_draft_opens_editable_and_may_start_once_its_plan_is_judged(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")

    assert _mode(screen) is BotsUiState.EDITING_DRAFT
    assert _rule(screen, BotAction.START) == (
        False,
        "The market numbers for this symbol are still being read.",
    )
    screen.settle()

    assert _rule(screen, BotAction.START)[0]
    assert not _rule(screen, BotAction.PAUSE)[0]
    assert "draft" in _rule(screen, BotAction.PAUSE)[1]
    assert screen.view.model.verdict_lines
    assert (
        screen.view._kind_panel is not None
        and screen.view._kind_panel.lower_price.isEnabled()
    )


def test_a_refused_plan_disables_start_and_says_why(open_bots_screen, qtbot) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT, REFUSED_CONFIG)])
    screen.settle()
    _select(screen, "a00001")

    enabled, reason = _rule(screen, BotAction.START)
    assert not enabled
    assert reason.startswith("Refused:")
    assert "minimum" in reason
    assert any(line.startswith("Refused:") for line in screen.view.model.verdict_lines)


def test_an_edit_waits_for_save_then_save_stores_the_parameters(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    _select(screen, "a00001")
    panel = screen.view._kind_panel
    assert panel is not None

    panel.capital.setText("1500")
    panel.capital.textEdited.emit("1500")
    qtbot.waitUntil(lambda: not _rule(screen, BotAction.START)[0])
    assert _rule(screen, BotAction.START)[1] == "Save the changed parameters first."

    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    assert _mode(screen) is BotsUiState.ACTION_IN_FLIGHT
    screen.settle()

    assert (
        screen.store.load(BotId("a00001")).bot.definition.config["capital_quote"]
        == "1500"
    )
    qtbot.waitUntil(lambda: _rule(screen, BotAction.START)[0])
    assert _mode(screen) is BotsUiState.EDITING_DRAFT


def test_a_running_bot_offers_pause_and_stop_and_its_parameters_are_read_only(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING)])
    screen.settle()
    _select(screen, "a00001")

    assert _mode(screen) is BotsUiState.VIEWING
    live = {action for action in BotAction if _rule(screen, action)[0]}
    assert live == {BotAction.PAUSE, BotAction.STOP}
    assert screen.view._kind_panel is not None
    assert not screen.view._kind_panel.lower_price.isEnabled()


def test_cancelling_the_stop_question_sends_nothing(open_bots_screen, qtbot) -> None:
    answers = Answers(stop=None)
    screen = open_bots_screen([stored("a00001", S.RUNNING)], answers)
    screen.settle()
    _select(screen, "a00001")

    screen.view.model.action_requested.emit(BotAction.STOP.value)

    assert answers.asked == ["stop a00001"]
    assert screen.pool.pending == []
    assert _mode(screen) is BotsUiState.VIEWING
    assert screen.store.load(BotId("a00001")).bot.state is S.RUNNING


def test_delete_asks_and_removes_the_bot_only_on_yes(open_bots_screen, qtbot) -> None:
    answers = Answers(delete=False)
    screen = open_bots_screen([stored("a00001", S.STOPPED)], answers)
    screen.settle()
    _select(screen, "a00001")

    screen.view.model.action_requested.emit(BotAction.DELETE.value)
    assert screen.pool.pending == []

    answers.delete = True
    screen.view.model.action_requested.emit(BotAction.DELETE.value)
    screen.settle()
    qtbot.waitUntil(lambda: screen.view.model.bots == ())

    assert answers.asked == ["delete a00001", "delete a00001"]
    assert not screen.store.exists(BotId("a00001"))
    assert screen.view.model.selected is None
    assert _mode(screen) is BotsUiState.NO_SELECTION


def test_a_new_bot_is_saved_as_a_draft_and_selected(open_bots_screen, qtbot) -> None:
    command = CreateBotCommand("my grid", "grid", VENUE, SYMBOL, GOOD_CONFIG)
    answers = Answers(new_bot=command)
    screen = open_bots_screen(answers=answers)
    screen.settle()

    screen.view.model.new_bot_requested.emit()
    screen.settle()
    qtbot.waitUntil(lambda: screen.view.model.selected is not None)
    screen.settle()

    assert answers.asked == [f"new bot ['grid'] ['{VENUE.value}']"]
    selected = screen.view.model.selected
    assert selected is not None and selected.name == "my grid"
    assert selected.state is S.DRAFT
    assert _mode(screen) is BotsUiState.EDITING_DRAFT
    assert screen.view.status.text() == "Create my grid: done."


def test_a_bot_created_with_the_minimum_is_completed_in_its_draft(
    open_bots_screen, qtbot
) -> None:
    """`BOT-150` — New bot saves no parameters; the draft is selected, Start
    names what to set, and the parameters typed there are saved."""
    answers = Answers(new_bot=CreateBotCommand("bare", "grid", VENUE, SYMBOL))
    screen = open_bots_screen(answers=answers)
    screen.settle()
    screen.view.model.new_bot_requested.emit()
    screen.settle()
    qtbot.waitUntil(lambda: screen.view.model.selected is not None)
    screen.settle()

    assert _mode(screen) is BotsUiState.EDITING_DRAFT
    enabled, reason = _rule(screen, BotAction.START)
    assert not enabled
    assert "Set the lower price, upper price and capital" in reason
    panel = screen.view._kind_panel
    assert panel is not None and panel.lower_price.isEnabled()

    for field, text in (
        (panel.lower_price, GOOD_CONFIG["lower"]),
        (panel.upper_price, GOOD_CONFIG["upper"]),
        (panel.capital, GOOD_CONFIG["capital_quote"]),
    ):
        field.setText(text)
        field.textEdited.emit(text)
    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.settle()

    bot_id = screen.view.model.selected.bot_id
    saved = screen.store.load(BotId(bot_id)).bot.definition.config
    assert saved == GOOD_CONFIG
    qtbot.waitUntil(lambda: _rule(screen, BotAction.START)[0])


def test_one_action_at_a_time_locks_the_list_and_every_action(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    _select(screen, "a00001")

    screen.view.model.action_requested.emit(BotAction.SAVE.value)

    assert not screen.view.table.isEnabled()
    assert not screen.actions.action(NEW_BOT).isEnabled()
    assert not any(
        screen.actions.action(lifecycle_id(action)).isEnabled() for action in BotAction
    )
    screen.view.model.action_requested.emit(BotAction.DELETE.value)
    assert len(screen.pool.pending) == 1  # the second click queued nothing


def test_a_read_for_the_bot_left_behind_is_dropped(open_bots_screen, qtbot) -> None:
    screen = open_bots_screen(
        [stored("a00001", S.DRAFT), stored("a00002", S.DRAFT, REFUSED_CONFIG)],
    )
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.view.model.select_requested.emit("a00002")

    late = next(
        index
        for index, (_, args) in enumerate(screen.pool.pending)
        if args[:1] == (ReadKind.PLANNER,) and args[2] == "a00001"
    )
    screen.pool.run(late)  # the first bot's planner read answers late

    assert screen.view.model.selected is not None
    assert screen.view.model.selected.bot_id == "a00002"
    assert screen.view.model.verdict_lines == ()
    screen.settle()
    assert _rule(screen, BotAction.START)[1].startswith("Refused:")


def test_an_answer_after_the_screen_closed_is_dropped(open_bots_screen, qtbot) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    _select(screen, "a00001")
    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    status = screen.view.model.statusMessage

    screen.presenter.dispose()
    screen.settle()

    assert screen.view.model.statusMessage == status


def test_a_write_by_anyone_else_is_read_again(open_bots_screen, qtbot) -> None:
    """A bot's worker saves from its own thread; the store announces it and
    the screen reads the list again (coalesced), no click needed."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    screen.store.save(stored("a00009", S.DRAFT))
    qtbot.waitUntil(lambda: bool(screen.pool.pending))
    screen.settle()

    assert {bot.bot_id for bot in screen.view.model.bots} == {"a00001", "a00009"}


def test_fit_levels_scales_the_selected_bots_chart_to_its_levels(
    open_bots_screen, qtbot
) -> None:
    """`EPIC-033K`: Fit levels, a command now, reaches the chart in the
    centre; the draft's levels run from 60,000 to 70,000, and nothing has
    scaled the price axis to them before."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    _select(screen, "a00001")
    card = screen.view.chart_area.findChild(ChartCard)
    assert card is not None
    axis = card.plot_layout.main_plot.vb
    # Before Fit levels the price axis is pyqtgraph's empty default.
    assert axis.viewRange()[1] == [0, 1]

    screen.actions.action(FIT_LEVELS).trigger()

    low, high = axis.viewRange()[1]
    assert low <= 60000 and high >= 70000


def test_a_write_still_queued_when_the_screen_closes_arms_nothing(
    open_bots_screen, qtbot
) -> None:
    """`BUG-149`: a bot's worker saves from its own thread, so the change
    reaches the screen queued. Delivered after the screen closed, it must not
    re-arm the coalesced re-read, which would submit into a pool that has shut
    down by the time it fires."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    worker = threading.Thread(
        target=screen.store.save, args=(stored("a00009", S.DRAFT),)
    )
    worker.start()
    worker.join()

    screen.presenter.dispose()
    QCoreApplication.processEvents()

    assert [t for t in screen.presenter.findChildren(QTimer) if t.isActive()] == []
    assert screen.pool.pending == []


def test_a_bot_deleted_while_an_action_is_in_flight_leaves_no_detail_behind(
    open_bots_screen, qtbot
) -> None:
    """PR #333 review: a list read that lands during an action and no longer
    finds the selected bot must not leave that bot's facts and actions on
    screen once the action settles."""
    answers = Answers(delete=True)
    screen = open_bots_screen(
        [stored("a00001", S.STOPPED), stored("a00002", S.DRAFT)], answers
    )
    screen.settle()
    _select(screen, "a00001")
    screen.view.model.action_requested.emit(BotAction.DELETE.value)
    assert _mode(screen) is BotsUiState.ACTION_IN_FLIGHT

    screen.store.delete(BotId("a00001"))  # the delete lands before its answer
    qtbot.waitUntil(lambda: len(screen.pool.pending) == 2)
    screen.pool.run(1)  # the re-read the store's announcement queued
    screen.settle()

    model = screen.view.model
    assert model.selected is None
    assert model.facts is None
    assert not any(rule.enabled for rule in model.availability.values())
    assert _mode(screen) is BotsUiState.NO_SELECTION


def test_after_save_the_screen_follows_the_stored_parameters(
    open_bots_screen, qtbot
) -> None:
    """Once Save is accepted the edits are dropped: a later write to the bot's
    parameters (from anywhere) is what the screen judges, not the old edits."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    _select(screen, "a00001")
    panel = screen.view._kind_panel
    assert panel is not None
    panel.capital.setText("1500")
    panel.capital.textEdited.emit("1500")
    screen.view.model.action_requested.emit(BotAction.SAVE.value)
    screen.settle()

    screen.store.save(
        stored("a00001", S.DRAFT, {**GOOD_CONFIG, "capital_quote": "1200"})
    )
    qtbot.waitUntil(lambda: bool(screen.pool.pending))
    screen.settle()

    assert _rule(screen, BotAction.START)[0]
