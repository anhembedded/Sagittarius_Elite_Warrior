"""`EPIC-047E` - its commands: the Bots screen's doors on the far side of the real bridge session.

The business promise: a screen that asks its dispatcher what it always asked gets the host's published answer, with the
host's words where the host never published; a command reaches the host's own gate as the request the `bot` verb of the
same name sends, once, only while the link is up, and the host's answer comes back in the screen's result.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_command_dispatcher import (
    DISCONNECTED_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_requests import (
    NOT_CARRIED_RENAME,
    NOT_CARRIED_START_EDITS,
    proposal_in,
    request_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot_for_host.handler import (
    _proposed_words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import (
    NOT_PUBLISHED_BY_THE_HOST,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.resume_proposal_summary import (
    ResumeProposalSummary,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.dispatcher_world import (
    BTC,
    ETH,
    BlockingDoor,
    ask,
    build_dispatcher,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    VpsHost,
    VpsTabWorld,
)

# -- commands --------------------------------------------------------------------------------


def test_stop_reaches_the_hosts_door_as_the_stop_verb_and_returns_the_hosts_words(
    tab: VpsTabWorld,
) -> None:
    dispatcher, _ = build_dispatcher(tab)

    result = dispatcher.dispatch(
        StopBotCommand,
        StopBotCommand(BTC.bot_id, ExposureHandling.CLOSE_AT_MARKET),
    )

    (_, request, _) = tab.host.door.sent[0]
    assert request == HostControlRequest(
        HostControlAction.STOP, BTC.bot_id, None, close_position=True
    )
    assert result == BotCommandResult(
        accepted=True, bot_id="b-0001", message=tab.host.door.reply.message
    )


def test_the_answer_to_the_real_money_question_travels_as_the_venue_typed(
    tab: VpsTabWorld,
) -> None:
    dispatcher, _ = build_dispatcher(tab)

    dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    dispatcher.dispatch(
        StartBotCommand, StartBotCommand(ETH.bot_id, real_money_confirmed=True)
    )

    refused, confirmed = (sent[1] for sent in tab.host.door.sent)
    assert refused.confirmed_venue is None
    assert confirmed.confirmed_venue == ETH.venue.value


def test_a_host_refusal_comes_back_in_the_hosts_words_and_is_not_retried(
    tab: VpsTabWorld,
) -> None:
    tab.host.door.reply = HostControlReply(
        HostControlStatus.REFUSED, "Bot b-0002 trades real money.", "c" * 32, "b-0002"
    )
    dispatcher, _ = build_dispatcher(tab)

    result = dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))

    assert not isinstance(result, BotCommandResult) or not result.accepted
    assert result.message == "Bot b-0002 trades real money."  # type: ignore[attr-defined]
    assert len(tab.host.door.sent) == 1


def test_a_start_that_carries_unsaved_edits_is_refused_before_the_host(
    tab: VpsTabWorld,
) -> None:
    dispatcher, _ = build_dispatcher(tab)

    result = dispatcher.dispatch(
        StartBotCommand, StartBotCommand(ETH.bot_id, {"lower": "1"})
    )

    assert result.message == NOT_CARRIED_START_EDITS  # type: ignore[attr-defined]
    assert tab.host.door.sent == []


def test_an_edit_sends_only_what_changed(tab: VpsTabWorld) -> None:
    dispatcher, _ = build_dispatcher(tab)
    config = dict(ETH.config)
    key = next(iter(config)) if config else "grid_count"
    changed = {**config, key: "99"}

    unchanged = dispatcher.dispatch(
        EditBotCommand, EditBotCommand(ETH.bot_id, ETH.name, config)
    )
    dispatcher.dispatch(EditBotCommand, EditBotCommand(ETH.bot_id, ETH.name, changed))
    renamed = dispatcher.dispatch(
        EditBotCommand, EditBotCommand(ETH.bot_id, "other", config)
    )

    assert unchanged.accepted  # type: ignore[attr-defined]
    (sent,) = tab.host.door.sent
    assert [(s.key, s.value) for s in sent[1].settings] == [(key, "99")]
    assert renamed.message == NOT_CARRIED_RENAME  # type: ignore[attr-defined]


def test_a_command_on_a_bot_the_host_does_not_list_is_not_sent(
    tab: VpsTabWorld,
) -> None:
    dispatcher, _ = build_dispatcher(tab)

    result = dispatcher.dispatch(
        StopBotCommand, StopBotCommand("b-9999", ExposureHandling.KEEP)
    )

    assert not result.accepted  # type: ignore[attr-defined]
    assert tab.host.door.sent == []


def test_while_disconnected_queries_answer_the_last_data_and_commands_are_not_sent() -> (
    None
):
    tab = VpsTabWorld(hold_after_cut=True).start()
    dispatcher, _ = build_dispatcher(tab)
    tab.cut()
    tab.wait_down()

    listed = ask(dispatcher, ListBotsQuery())
    refused = dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
    tab.stop()

    assert {bot.bot_id for bot in listed.bots} == {BTC.bot_id, ETH.bot_id}  # type: ignore[attr-defined]
    assert refused.message == DISCONNECTED_WORDS  # type: ignore[attr-defined]
    assert refused.refusal is None  # type: ignore[attr-defined]
    assert tab.host.door.sent == []


def test_a_command_in_flight_when_the_link_is_cut_is_never_sent_again() -> None:
    host = VpsHost()
    door = BlockingDoor()
    host.door = door
    tab = VpsTabWorld(host).start()
    dispatcher, _ = build_dispatcher(tab)
    outcome: list[object] = []
    sender = threading.Thread(
        target=lambda: outcome.append(
            dispatcher.dispatch(StartBotCommand, StartBotCommand(ETH.bot_id))
        )
    )
    sender.start()
    assert door.arrived.wait(timeout=5)

    tab.cut()
    sender.join(timeout=10)
    tab.wait_up()  # the supervisor redials at once
    door.release.set()
    tab.stop()

    (result,) = outcome
    assert not result.accepted  # type: ignore[attr-defined]
    assert door.sent[0][0] in result.message  # type: ignore[attr-defined]
    assert len(door.sent) == 1
    assert [u.request_id for u in tab.unanswered.entries()] == [door.sent[0][0]]


def test_a_bot_the_host_never_read_shows_a_gap_in_words_not_a_default(
    tab: VpsTabWorld,
) -> None:
    dispatcher, _ = build_dispatcher(tab)
    tab.host.bots.put(replace(ETH, bot_id="b-0004"))
    tab.wait_bot_changed()

    fills = ask(dispatcher, GetBotFillsQuery("b-0004"))
    exchange = ask(dispatcher, GetExchangeFactsQuery("b-0004"))

    assert fills.problem == NOT_PUBLISHED_BY_THE_HOST  # type: ignore[attr-defined]
    assert exchange.reason == NOT_PUBLISHED_BY_THE_HOST  # type: ignore[attr-defined]


# -- the confirmation of a resume proposal ---------------------------------------------------


def test_the_fingerprint_is_read_from_the_sentence_the_host_really_writes() -> None:

    held = ResumeProposalSummary("1a2b3c4d", 12, Decimal("100.5"), Decimal(3))

    assert proposal_in(_proposed_words("b-0001", held, "futures_mainnet")) == "1a2b3c4d"
    assert proposal_in("stopped") is None


def test_confirm_resume_lays_the_proposal_the_screen_was_shown_and_no_other(
    tab: VpsTabWorld,
) -> None:

    dispatcher, _ = build_dispatcher(tab)
    tab.host.door.reply = HostControlReply(
        HostControlStatus.DONE,
        "bot b-0001 proposes 3 orders from 1 with 0 held; nothing is placed yet. Fingerprint 0a1b2c3d. Read it",
        "c" * 32,
        "b-0001",
    )
    dispatcher.dispatch(ResumeBotCommand, ResumeBotCommand(BTC.bot_id))
    dispatcher.dispatch(ConfirmBotResumeCommand, ConfirmBotResumeCommand(BTC.bot_id))

    confirm = tab.host.door.sent[1][1]
    assert confirm.action is HostControlAction.CONFIRM_RESUME
    assert confirm.proposal == "0a1b2c3d"


def test_a_second_command_on_a_bot_whose_last_one_is_lost_is_refused_not_sent() -> None:
    host = VpsHost()
    door = BlockingDoor()
    host.door = door
    tab = VpsTabWorld(host).start()
    dispatcher, _ = build_dispatcher(tab)
    first = threading.Thread(
        target=lambda: dispatcher.dispatch(
            StopBotCommand, StopBotCommand(ETH.bot_id, ExposureHandling.KEEP)
        )
    )
    first.start()
    assert door.arrived.wait(timeout=5)
    tab.cut()
    first.join(timeout=10)
    tab.wait_up()  # the supervisor redials; the new link does not settle the lost command
    door.release.set()

    again = dispatcher.dispatch(
        StopBotCommand, StopBotCommand(ETH.bot_id, ExposureHandling.KEEP)
    )
    elsewhere = dispatcher.dispatch(PauseBotCommand, PauseBotCommand(BTC.bot_id))
    tab.stop()

    lost_id = door.sent[0][0]
    assert not again.accepted  # type: ignore[attr-defined]
    assert lost_id in again.message  # type: ignore[attr-defined]
    assert elsewhere.accepted  # type: ignore[attr-defined]
    assert [s[1].bot_id for s in door.sent] == [ETH.bot_id, BTC.bot_id]


@pytest.mark.parametrize(
    ("command", "sends_the_venue"),
    [
        (StartBotCommand(ETH.bot_id), False),
        (StartBotCommand(ETH.bot_id, real_money_confirmed=True), True),
        (ResumeBotCommand(ETH.bot_id), False),
        (ResumeBotCommand(ETH.bot_id, real_money_confirmed=True), True),
        (StopBotCommand(ETH.bot_id, ExposureHandling.KEEP), False),
        (
            StopBotCommand(
                ETH.bot_id, ExposureHandling.KEEP, real_money_confirmed=True
            ),
            True,
        ),
        (ConfirmBotResumeCommand(ETH.bot_id, "0a1b2c3d"), False),
        (
            ConfirmBotResumeCommand(ETH.bot_id, "0a1b2c3d", real_money_confirmed=True),
            True,
        ),
    ],
    ids=[
        "start",
        "start-yes",
        "resume",
        "resume-yes",
        "stop",
        "stop-yes",
        "confirm",
        "confirm-yes",
    ],
)
def test_the_venue_is_typed_only_when_the_person_answered_the_question(
    command: object, sends_the_venue: bool
) -> None:
    sent = request_of(command, {ETH.bot_id: ETH})

    assert isinstance(sent, HostControlRequest)
    assert (sent.confirmed_venue == ETH.venue.value) is sends_the_venue
    assert sent.confirmed_venue is None or sent.confirmed_venue == ETH.venue.value
