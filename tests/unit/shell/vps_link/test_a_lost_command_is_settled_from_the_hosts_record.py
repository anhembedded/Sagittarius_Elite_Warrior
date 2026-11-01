"""`EPIC-047E` (AC6, decision of 2026-10-28) - after a cut, what became of a lost command is read from the host, never re-run.

The business promise: a command whose answer was lost with the link is settled from what the host recorded for its request
id (read-only); the person is told in the host's words whether it ran, or that it never reached the host and may be sent
again; the bot's block lifts only then; and nothing in this path sends a command again, so a lost Start cannot run late.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.command_reconciler import (
    CommandReconciler,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    ETH,
    a_lost_start_then_back_up,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld


def _reconciler(tab: VpsTabWorld) -> tuple[CommandReconciler, list[str]]:
    told: list[str] = []
    return CommandReconciler(tab.unanswered, tab.control, told.append), told


def test_a_command_the_host_ran_is_settled_with_the_hosts_words_and_the_bot_is_free() -> (
    None
):
    tab, door, dispatcher = a_lost_start_then_back_up()
    reconciler, told = _reconciler(tab)
    request_id = door.sent[0][0]

    remaining = reconciler.reconcile()
    free = dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    tab.stop()

    assert remaining == 0
    assert tab.unanswered.entries() == ()
    assert len(told) == 1
    assert "start on b-0002" in told[0]
    assert "ran on the host" in told[0]
    assert door.asked == [request_id]
    assert free.accepted  # type: ignore[attr-defined]


def test_a_command_the_host_refused_is_told_as_not_run() -> None:
    tab, door, _ = a_lost_start_then_back_up()
    door.outcomes[door.sent[0][0]] = HostControlReply(
        HostControlStatus.REFUSED, "Bot b-0002 trades real money.", "c" * 32, "b-0002"
    )
    reconciler, told = _reconciler(tab)

    reconciler.reconcile()
    tab.stop()

    assert tab.unanswered.entries() == ()
    assert "did not run" in told[0]
    assert "Bot b-0002 trades real money." in told[0]


def test_a_command_the_host_never_saw_is_settled_as_not_sent_and_is_not_sent_again() -> (
    None
):
    tab, door, _ = a_lost_start_then_back_up()
    door.outcomes[door.sent[0][0]] = None
    reconciler, told = _reconciler(tab)

    reconciler.reconcile()
    tab.stop()

    assert tab.unanswered.entries() == ()
    assert "never reached the host" in told[0]
    assert "Send it again if you still want it" in told[0]
    assert len(door.sent) == 1  # only the original: the reconcile re-sent nothing


def test_while_the_host_has_recorded_nothing_the_bot_stays_blocked_and_nothing_is_told() -> (
    None
):
    tab, door, dispatcher = a_lost_start_then_back_up()
    door.outcomes[door.sent[0][0]] = HostControlReply(
        HostControlStatus.NO_ANSWER, "The host took the command.", "c" * 32
    )
    reconciler, told = _reconciler(tab)

    remaining = reconciler.reconcile()
    still_blocked = dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    tab.stop()

    assert remaining == 1
    assert told == []
    assert not still_blocked.accepted  # type: ignore[attr-defined]


def test_with_the_link_down_nothing_is_settled_and_the_person_is_told_it_could_not_be_checked() -> (
    None
):
    tab, _, _ = a_lost_start_then_back_up()
    tab.stop()
    reconciler, told = _reconciler(tab)

    remaining = reconciler.reconcile()

    assert remaining == 1
    assert "could not be checked" in told[0]
    assert len(tab.unanswered.entries()) == 1


def test_two_reconciles_of_one_command_tell_the_person_once() -> None:
    """A second pass that finds the entry already settled says nothing (`settle` reports whether it removed it)."""
    tab, door, _ = a_lost_start_then_back_up()
    _, told = _reconciler(tab)
    second = CommandReconciler(tab.unanswered, tab.control, told.append)
    request_id = door.sent[0][0]
    entry = tab.unanswered.entries()[0]

    assert tab.unanswered.settle(request_id) is True
    second._settle(entry, None)
    tab.stop()

    assert told == []
    assert tab.unanswered.settle(request_id) is False
