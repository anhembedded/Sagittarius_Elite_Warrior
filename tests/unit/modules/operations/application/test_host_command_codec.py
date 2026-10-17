"""`EPIC-038J` - the wire form of a command: strict on the way in, exact on the way out."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    MalformedDocument,
    encode_command,
    parse_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HostCommand,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    ID_A,
    command,
)


def _document(**overrides: object) -> str:
    base: dict[str, object] = {
        "schema": "sew.host-command/1",
        "command_id": ID_A,
        "action": "stop",
        "bot_id": "44wa1x",
        "confirmed_venue": None,
        "issued_at": "2026-10-17T12:00:00+00:00",
    }
    base.update(overrides)
    return json.dumps(base)


def test_a_command_survives_the_round_trip() -> None:
    sent = command(
        action=HostControlAction.RESUME, confirmed_venue="spot_mainnet", bot_id="abc123"
    )

    assert parse_command(encode_command(sent)) == sent


def test_a_valid_document_is_a_command() -> None:
    parsed = parse_command(_document())

    assert isinstance(parsed, HostCommand)
    assert (parsed.action, parsed.bot_id) == (HostControlAction.STOP, "44wa1x")


def test_a_stop_that_closes_the_position_survives_the_round_trip() -> None:
    sent = command(close_position=True)

    assert parse_command(encode_command(sent)) == sent


def test_a_command_that_does_not_close_is_the_document_an_older_host_reads() -> None:
    """`BUG-224`: the key is written only when true, so nothing else changes on the wire."""
    assert "close_position" not in json.loads(encode_command(command()))
    parsed = parse_command(_document())
    assert isinstance(parsed, HostCommand) and parsed.close_position is False


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("not json", "JSON"),
        ("[]", "object"),
        (_document(schema="sew.host-command/2"), "schema"),
        (_document(action="restart"), "action"),
        (_document(action="Start"), "action"),
        (_document(action=5), "action"),
        (_document(command_id="short"), "command_id"),
        (_document(command_id="G" * 32), "command_id"),
        (_document(bot_id="../etc/passwd"), "bot_id"),
        (_document(bot_id=""), "bot_id"),
        (_document(bot_id="x" * 65), "bot_id"),
        (_document(confirmed_venue=7), "confirmed_venue"),
        (_document(issued_at="yesterday"), "issued_at"),
        (_document(issued_at="2026-10-17T12:00:00"), "issued_at"),
        (_document(extra="x"), "unknown"),
        (_document(close_position="yes"), "close_position"),
        (_document(close_position=1), "close_position"),
        (_document(action="pause", close_position=True), "close_position"),
        (_document(action="start", close_position=True), "close_position"),
        (_document(action="delete", close_position=True), "close_position"),
    ],
)
def test_a_document_that_is_not_exactly_a_command_is_malformed(
    text: str, why: str
) -> None:
    parsed = parse_command(text)

    assert isinstance(parsed, MalformedDocument)
    assert why in parsed.reason


def test_a_malformed_document_still_names_its_id_when_that_part_is_sound() -> None:
    parsed = parse_command(_document(action="restart"))

    assert isinstance(parsed, MalformedDocument)
    assert parsed.command_id == ID_A


def test_a_document_without_a_sound_id_names_none() -> None:
    parsed = parse_command(_document(command_id="x"))

    assert isinstance(parsed, MalformedDocument)
    assert parsed.command_id == ""


@pytest.mark.parametrize("action", [HostControlAction.START, HostControlAction.DELETE])
def test_a_start_or_a_delete_survives_the_round_trip(action: HostControlAction) -> None:
    sent = command(action=action, confirmed_venue="futures_mainnet")

    assert parse_command(encode_command(sent)) == sent


@pytest.mark.parametrize("word", ["start", "delete"])
def test_the_new_actions_are_new_words_not_new_keys(word: str) -> None:
    """`EPIC-038K`: an older host reads the same keys and a word it does not know, so it refuses
    the document as malformed (REJECTED, audited, nothing executed) instead of misreading it."""
    document = json.loads(encode_command(command(action=HostControlAction(word))))

    assert set(document) == {
        "schema",
        "command_id",
        "action",
        "bot_id",
        "confirmed_venue",
        "issued_at",
    }
    assert document["action"] == word


def test_the_refusal_of_an_unknown_action_lists_every_action_the_host_knows() -> None:
    parsed = parse_command(_document(action="restart"))

    assert isinstance(parsed, MalformedDocument)
    for action in HostControlAction:
        assert action.value in parsed.reason
