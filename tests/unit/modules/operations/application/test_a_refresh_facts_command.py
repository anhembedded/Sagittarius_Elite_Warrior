"""`EPIC-047H` - `bot refresh-facts`: strict on the way in, queued and never run on the poller's thread, worded for the operator."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_host_command_executor import (
    BotHostCommandExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    MalformedDocument,
    encode_command,
    parse_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_facts_refresh_requests import (
    IFactsRefreshRequests,
    RefreshRequestAnswer,
    RefreshRequestVerdict,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    ID_A,
    command,
)

READ_AT = datetime(2026, 10, 27, 9, 30, tzinfo=UTC)


class _Dispatcher(ICommandDispatcher):
    def __init__(self) -> None:
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        raise AssertionError("a refresh dispatches no bot command")


class _Refresh(IFactsRefreshRequests):
    def __init__(
        self, verdict: RefreshRequestVerdict, read_at: datetime | None = None
    ) -> None:
        self.asked: list[str] = []
        self._answer = RefreshRequestAnswer(verdict, read_at)

    def request(self, bot_id: str) -> RefreshRequestAnswer:
        self.asked.append(bot_id)
        return self._answer


def _document(**overrides: object) -> str:
    base: dict[str, object] = {
        "schema": "sew.host-command/1",
        "command_id": ID_A,
        "action": "refresh-facts",
        "bot_id": "44wa1x",
        "confirmed_venue": None,
        "issued_at": "2026-10-17T12:00:00+00:00",
    }
    base.update(overrides)
    return json.dumps(base)


def test_a_refresh_survives_the_round_trip() -> None:
    sent = command(action=HostControlAction.REFRESH_FACTS, bot_id="abc123")

    assert parse_command(encode_command(sent)) == sent


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirmed_venue": "spot_mainnet"},
        {"close_position": True},
        {"set": {"lower": "1"}},
        {"to_venue": "spot_testnet"},
    ],
    ids=["venue", "close-position", "set", "to-venue"],
)
def test_a_refresh_carries_nothing_that_acts_on_a_bot(
    overrides: dict[str, object],
) -> None:
    assert isinstance(parse_command(_document(**overrides)), MalformedDocument)


def test_a_refresh_is_queued_and_dispatches_no_bot_command() -> None:
    dispatcher, refresh = _Dispatcher(), _Refresh(RefreshRequestVerdict.QUEUED)

    outcome = BotHostCommandExecutor(dispatcher, refresh).execute(
        command(action=HostControlAction.REFRESH_FACTS, bot_id="abc123")
    )

    assert outcome.accepted
    assert refresh.asked == ["abc123"]
    assert dispatcher.dispatched == []


def test_inside_thirty_seconds_the_answer_says_already_fresh_and_when() -> None:
    refresh = _Refresh(RefreshRequestVerdict.ALREADY_FRESH, READ_AT)

    outcome = BotHostCommandExecutor(_Dispatcher(), refresh).execute(
        command(action=HostControlAction.REFRESH_FACTS, bot_id="abc123")
    )

    assert outcome.accepted
    assert "already fresh" in outcome.message
    assert str(READ_AT) in outcome.message


@pytest.mark.parametrize(
    ("verdict", "words"),
    [
        (RefreshRequestVerdict.OFF, "refresh is off"),
        (RefreshRequestVerdict.UNKNOWN_BOT, "no bot has that id"),
    ],
)
def test_a_refresh_that_cannot_be_made_is_refused_in_words(
    verdict: RefreshRequestVerdict, words: str
) -> None:
    outcome = BotHostCommandExecutor(_Dispatcher(), _Refresh(verdict)).execute(
        command(action=HostControlAction.REFRESH_FACTS, bot_id="abc123")
    )

    assert not outcome.accepted
    assert words in outcome.message


def test_a_host_without_a_refresh_refuses_it_and_places_nothing() -> None:
    dispatcher = _Dispatcher()

    outcome = BotHostCommandExecutor(dispatcher).execute(
        command(action=HostControlAction.REFRESH_FACTS, bot_id="abc123")
    )

    assert not outcome.accepted
    assert dispatcher.dispatched == []
