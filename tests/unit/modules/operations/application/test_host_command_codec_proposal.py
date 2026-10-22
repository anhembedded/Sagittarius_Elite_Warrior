"""`EPIC-045G` - the wire form of a confirm-resume's `proposal` (the fingerprint of what a person read)."""

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

CONFIRM = HostControlAction.CONFIRM_RESUME


def _document(**overrides: object) -> str:
    base: dict[str, object] = {
        "schema": "sew.host-command/1",
        "command_id": ID_A,
        "action": "confirm-resume",
        "bot_id": "44wa1x",
        "confirmed_venue": None,
        "issued_at": "2026-10-21T12:00:00+00:00",
        "proposal": "1a2b3c4d",
    }
    base.update(overrides)
    return json.dumps(base)


def test_a_confirmation_with_its_proposal_survives_the_round_trip() -> None:
    sent = command(action=CONFIRM, proposal="1a2b3c4d", confirmed_venue="spot_mainnet")

    assert parse_command(encode_command(sent)) == sent


def test_a_confirmation_with_no_proposal_is_a_sound_document_the_host_refuses_in_words() -> (
    None
):
    sent = command(action=CONFIRM)

    assert "proposal" not in json.loads(encode_command(sent))
    assert parse_command(encode_command(sent)) == sent


def test_the_new_key_is_written_only_when_set_so_every_other_document_is_unchanged() -> (
    None
):
    for action in HostControlAction:
        assert "proposal" not in json.loads(encode_command(command(action=action)))


@pytest.mark.parametrize(
    "proposal",
    [None, 5, "", "abc", "1A2B3C4D", "1a2b3c4d5e6f7a8b9", "not hex!!", "1a2b 3c4d"],
    ids=[
        "null",
        "number",
        "empty",
        "too-short",
        "capitals",
        "too-long",
        "text",
        "space",
    ],
)
def test_a_proposal_that_is_not_a_short_hex_fingerprint_is_malformed(
    proposal: object,
) -> None:
    assert isinstance(parse_command(_document(proposal=proposal)), MalformedDocument)


@pytest.mark.parametrize(
    "action", ["stop", "pause", "resume", "start", "delete", "move"]
)
def test_proposal_belongs_to_a_confirm_resume_alone(action: str) -> None:
    parsed = parse_command(_document(action=action))

    assert isinstance(parsed, MalformedDocument)
    assert "proposal" in parsed.reason or "to_venue" in parsed.reason
