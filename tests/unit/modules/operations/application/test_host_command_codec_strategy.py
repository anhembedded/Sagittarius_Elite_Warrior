"""`EPIC-045G` - the wire form of an arm-strategy's and a disarm-strategy's `strategy_venue`."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    STRATEGY_SUBJECT,
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    MalformedDocument,
    encode_command,
    parse_command,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    ID_A,
    command,
)

ARM = HostControlAction.ARM_STRATEGY
DISARM = HostControlAction.DISARM_STRATEGY


def _document(**overrides: object) -> str:
    base: dict[str, object] = {
        "schema": "sew.host-command/1",
        "command_id": ID_A,
        "action": "arm-strategy",
        "bot_id": STRATEGY_SUBJECT,
        "confirmed_venue": None,
        "issued_at": "2026-10-21T12:00:00+00:00",
        "strategy_venue": "spot_testnet",
    }
    base.update(overrides)
    return json.dumps(base)


@pytest.mark.parametrize(
    "sent",
    [
        command(action=ARM, bot_id=STRATEGY_SUBJECT, strategy_venue="spot_testnet"),
        command(
            action=ARM,
            bot_id=STRATEGY_SUBJECT,
            strategy_venue="spot_mainnet",
            confirmed_venue="spot_mainnet",
        ),
        command(action=DISARM, bot_id=STRATEGY_SUBJECT, strategy_venue="spot_mainnet"),
    ],
    ids=["arm", "arm-typed", "disarm"],
)
def test_an_arm_and_a_disarm_survive_the_round_trip(sent: object) -> None:
    assert parse_command(encode_command(sent)) == sent  # type: ignore[arg-type]


def test_the_new_key_is_written_only_when_set_so_every_other_document_is_unchanged() -> (
    None
):
    for action in HostControlAction:
        if action in (ARM, DISARM):
            continue
        assert "strategy_venue" not in json.loads(
            encode_command(command(action=action))
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"strategy_venue": None},
        {"strategy_venue": 5},
        {"strategy_venue": ""},
        {"strategy_venue": "Spot Testnet"},
        {"strategy_venue": "v" * 33},
        {"bot_id": "44wa1x"},
        {"bot_id": "new-bot"},
        {"set": {"lower": "1"}},
        {"close_position": True},
        {"to_venue": "spot_testnet"},
    ],
    ids=[
        "null",
        "number",
        "empty",
        "capitals-and-space",
        "too-long",
        "a-bot-id",
        "the-add-subject",
        "carries-a-set",
        "closes",
        "carries-a-move-key",
    ],
)
def test_an_arm_document_that_is_not_exactly_one_is_malformed(
    overrides: dict[str, object],
) -> None:
    assert isinstance(parse_command(_document(**overrides)), MalformedDocument)


def test_a_disarm_asks_no_venue_because_it_sells_and_cancels_nothing() -> None:
    document = _document(action="disarm-strategy", confirmed_venue="spot_mainnet")

    parsed = parse_command(document)

    assert isinstance(parsed, MalformedDocument) and "disarm" in parsed.reason


def test_an_arm_may_carry_the_typed_venue_and_the_host_judges_it() -> None:
    parsed = parse_command(_document(confirmed_venue="spot_testnet"))

    assert not isinstance(parsed, MalformedDocument)
    assert parsed.confirmed_venue == "spot_testnet"


@pytest.mark.parametrize("action", ["stop", "pause", "resume", "start", "delete"])
def test_strategy_venue_belongs_to_an_arm_and_a_disarm_alone(action: str) -> None:
    parsed = parse_command(_document(action=action, bot_id="44wa1x"))

    assert isinstance(parsed, MalformedDocument)
    assert "strategy_venue" in parsed.reason


def test_the_strategy_subject_names_no_bot_for_any_other_action() -> None:
    document = json.loads(_document(action="stop"))
    del document["strategy_venue"]

    refused = parse_command(json.dumps(document))

    assert isinstance(refused, MalformedDocument) and "not a bot id" in refused.reason
