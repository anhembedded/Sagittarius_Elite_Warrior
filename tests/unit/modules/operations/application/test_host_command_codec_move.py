"""`EPIC-045G` - the wire form of a move's `to_venue`."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import HostControlAction
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    MalformedDocument,
    encode_command,
    parse_command,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    ID_A,
    command,
)


def _document(**overrides: object) -> str:
    base: dict[str, object] = {
        "schema": "sew.host-command/1",
        "command_id": ID_A,
        "action": "move",
        "bot_id": "44wa1x",
        "confirmed_venue": None,
        "issued_at": "2026-10-21T12:00:00+00:00",
        "to_venue": "spot_mainnet",
    }
    base.update(overrides)
    return json.dumps(base)


def test_a_move_survives_the_round_trip() -> None:
    sent = command(action=HostControlAction.MOVE, to_venue="spot_mainnet")

    assert parse_command(encode_command(sent)) == sent


def test_a_move_adds_a_new_key_and_a_new_word_so_an_older_host_refuses_it_unread() -> (
    None
):
    document = json.loads(
        encode_command(command(action=HostControlAction.MOVE, to_venue="spot_mainnet"))
    )

    assert document["action"] == "move"
    assert set(document) - {
        "schema",
        "command_id",
        "action",
        "bot_id",
        "confirmed_venue",
        "issued_at",
    } == {"to_venue"}


def test_every_other_action_is_still_the_document_an_older_host_reads_after_a_move_was_added() -> (
    None
):
    for action in HostControlAction:
        if action is HostControlAction.MOVE:
            continue
        assert "to_venue" not in json.loads(encode_command(command(action=action)))


@pytest.mark.parametrize(
    "overrides",
    [
        {"to_venue": None},
        {"to_venue": 5},
        {"to_venue": ""},
        {"to_venue": "Spot Mainnet"},
        {"to_venue": "v" * 33},
        {"confirmed_venue": "spot_mainnet"},
        {"set": {"lower": "1"}},
        {"close_position": True},
        {"bot_id": "new-bot"},
        {"bot_id": "loss-cap"},
    ],
    ids=[
        "null",
        "number",
        "empty",
        "capitals-and-space",
        "too-long",
        "asks-a-venue",
        "carries-a-set",
        "closes",
        "the-add-subject",
        "the-loss-cap-subject",
    ],
)
def test_a_move_document_that_is_not_exactly_one_is_malformed(
    overrides: dict[str, object],
) -> None:
    assert isinstance(parse_command(_document(**overrides)), MalformedDocument)


def test_a_move_without_to_venue_is_malformed() -> None:
    document = json.loads(_document())
    del document["to_venue"]

    assert isinstance(parse_command(json.dumps(document)), MalformedDocument)


@pytest.mark.parametrize("action", ["stop", "pause", "resume", "start", "delete"])
def test_to_venue_belongs_to_a_move_alone(action: str) -> None:
    parsed = parse_command(_document(action=action))

    assert isinstance(parsed, MalformedDocument)
    assert "to_venue" in parsed.reason
