"""`EPIC-047E` - Bots → Add to VPS…, on the presenter's real wiring.

The business promise (charter Scenario 2): the bot designed in the Bots tab lands on the VPS host as a DRAFT with nothing copied by
hand. It asks first; it sends the selected bot's definition once, as the host's `add` verb, with no real-money confirmation (an add
places no order); the host's words come back; a reply that never came is never told as a failure; and the VPS tab, which already
shows the host's bots, does not offer it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    HostControlAction,
    HostControlReply,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.add_to_vps_flow import (
    UNKNOWN_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    ADD_TO_VPS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_backend import (
    NO_ADD_TO_VPS_HERE,
)

from .bots_screen_fixtures import Answers, BotsScreen, stored


def _failures(screen: BotsScreen) -> list[FailureNotice]:
    """Only Add to VPS's own: selecting a bot also raises the chart's stream notice."""
    return [n for n in screen.notifier.failures if n.cause == "bots.add_to_vps"]


def _screen(open_bots_screen, answers: Answers, *, select: bool = True) -> BotsScreen:
    screen = open_bots_screen(
        [
            stored("a00001", S.RUNNING, name="alpha grid"),
            stored("b00002", S.DRAFT, name="beta grid"),
        ],
        answers,
    )
    screen.settle()
    if select:
        screen.view.model.select_requested.emit("b00002")
        screen.settle()
    return screen


def test_add_to_vps_needs_a_selected_bot_and_says_why_not(open_bots_screen) -> None:
    screen = _screen(open_bots_screen, Answers(), select=False)
    command = screen.actions.action(ADD_TO_VPS)

    assert not command.isEnabled()
    assert "Select a bot first" in command.toolTip()

    screen.view.model.select_requested.emit("b00002")
    screen.settle()

    assert command.isEnabled()


def test_the_selected_bot_is_sent_once_as_the_hosts_add_with_no_real_money_question(
    open_bots_screen,
) -> None:
    answers = Answers(add_to_vps=True)
    screen = _screen(open_bots_screen, answers)

    screen.actions.action(ADD_TO_VPS).trigger()
    screen.settle()

    ((request, _wait),) = screen.vps.sent
    assert request.action is HostControlAction.ADD
    assert request.bot_id == ADD_SUBJECT
    assert request.confirmed_venue is None
    assert request.entry is not None
    assert request.entry.name == "beta grid"
    assert request.entry.venue == screen.view.model.selected.venue.identifier
    assert answers.asked[-1] == "add to vps b00002"


def test_the_hosts_own_words_are_told_and_the_bot_here_is_unchanged(
    open_bots_screen,
) -> None:
    screen = _screen(open_bots_screen, Answers(add_to_vps=True))

    screen.actions.action(ADD_TO_VPS).trigger()
    screen.settle()

    ((headline, detail),) = screen.notifier.events
    assert "beta grid" in headline and "DRAFT" in headline
    assert detail == "bot ab12cd was added as a DRAFT"
    assert screen.view.model.statusMessage == headline
    assert not _failures(screen)
    assert {"alpha grid", "beta grid"} <= {bot.name for bot in screen.view.model.bots}


def test_a_cancel_at_the_question_sends_nothing(open_bots_screen) -> None:
    screen = _screen(open_bots_screen, Answers(add_to_vps=False))

    screen.actions.action(ADD_TO_VPS).trigger()
    screen.settle()

    assert screen.vps.sent == []
    assert screen.notifier.events == []


def test_the_host_refusing_is_told_in_its_words_as_a_failure(open_bots_screen) -> None:
    screen = _screen(open_bots_screen, Answers(add_to_vps=True))
    screen.vps.reply = HostControlReply(
        HostControlStatus.REFUSED,
        "a bot named beta grid already exists on futures_testnet",
    )

    screen.actions.action(ADD_TO_VPS).trigger()
    screen.settle()

    (failure,) = _failures(screen)
    assert failure.kind is FailureKind.COMMAND
    assert "already exists" in failure.detail
    assert screen.view.model.statusIsError


def test_no_link_says_nothing_was_sent(open_bots_screen) -> None:
    screen = _screen(open_bots_screen, Answers(add_to_vps=True))
    screen.vps.reply = HostControlReply(
        HostControlStatus.NOT_RUNNING, "Not connected to the host: nothing was sent."
    )

    screen.actions.action(ADD_TO_VPS).trigger()
    screen.settle()

    (failure,) = _failures(screen)
    assert "nothing was sent" in failure.detail
    assert "may or may not" not in failure.headline


def test_a_reply_that_never_came_is_not_told_as_a_failure_to_create(
    open_bots_screen,
) -> None:
    screen = _screen(open_bots_screen, Answers(add_to_vps=True))
    screen.vps.reply = HostControlReply(
        HostControlStatus.NO_ANSWER, "the host did not answer in time"
    )

    screen.actions.action(ADD_TO_VPS).trigger()
    screen.settle()

    (failure,) = _failures(screen)
    assert failure.headline == UNKNOWN_WORDS.format(name="beta grid")
    assert len(screen.vps.sent) == 1


def test_a_second_press_while_one_waits_sends_nothing_more(open_bots_screen) -> None:
    screen = _screen(open_bots_screen, Answers(add_to_vps=True))
    command = screen.actions.action(ADD_TO_VPS)

    command.trigger()
    command.trigger()
    screen.settle()

    assert len(screen.vps.sent) == 1


def test_the_vps_tab_does_not_offer_it_and_says_where_it_is_done(
    open_bots_screen,
) -> None:
    screen = _screen(open_bots_screen, Answers(add_to_vps=True))
    screen.view.model.set_add_to_vps_unavailable(NO_ADD_TO_VPS_HERE)
    command = screen.actions.action(ADD_TO_VPS)

    assert not command.isEnabled()
    assert NO_ADD_TO_VPS_HERE in command.toolTip()
