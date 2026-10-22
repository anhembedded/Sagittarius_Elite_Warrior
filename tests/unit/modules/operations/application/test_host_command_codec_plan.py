"""`EPIC-045C` - the wire form of an apply-entry's `desired_state` and of an unplan."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    PLAN_SUBJECT,
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    MalformedDocument,
    encode_command,
    parse_command,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    ID_A,
    command,
)

APPLY = HostControlAction.APPLY_ENTRY
UNPLAN = HostControlAction.UNPLAN
_ENTRY = {
    "name": "sol grid",
    "kind": "grid",
    "venue": "spot_testnet",
    "symbol": "SOLUSDT",
    "params": {"lower": "80", "upper": "120"},
}


def _document(**overrides: object) -> str:
    base: dict[str, object] = {
        "schema": "sew.host-command/1",
        "command_id": ID_A,
        "action": "apply-entry",
        "bot_id": PLAN_SUBJECT,
        "confirmed_venue": None,
        "issued_at": "2026-10-22T12:00:00+00:00",
        "entry": dict(_ENTRY),
        "desired_state": "running",
    }
    base.update(overrides)
    return json.dumps(base)


def _reason(text: str) -> str:
    parsed = parse_command(text)
    assert isinstance(parsed, MalformedDocument)
    return parsed.reason


def test_an_apply_entry_survives_the_round_trip_with_its_wish() -> None:
    parsed = parse_command(_document(desired_state="stopped"))

    assert not isinstance(parsed, MalformedDocument)
    assert parsed.action is APPLY and parsed.desired_state == "stopped"
    assert parsed.entry is not None and isinstance(parsed.entry, NewBotEntry)
    assert parse_command(encode_command(parsed)) == parsed


def test_an_unplan_survives_the_round_trip() -> None:
    sent = command(action=UNPLAN, bot_id="44wa1x")

    assert parse_command(encode_command(sent)) == sent


def test_desired_state_is_written_only_when_set() -> None:
    for action in HostControlAction:
        if action is APPLY:
            continue
        assert "desired_state" not in json.loads(encode_command(command(action=action)))


@pytest.mark.parametrize(
    "overrides",
    [
        {"desired_state": None},
        {"desired_state": "paused"},
        {"desired_state": 1},
        {"bot_id": "44wa1x"},
        {"confirmed_venue": "spot_testnet"},
        {"set": {"lower": "1"}},
        {"close_position": True},
    ],
    ids=[
        "null",
        "unknown-word",
        "number",
        "a-bot-id",
        "asks-venue",
        "carries-set",
        "closes",
    ],
)
def test_an_apply_entry_that_is_not_exactly_one_is_malformed(
    overrides: dict[str, object],
) -> None:
    assert isinstance(parse_command(_document(**overrides)), MalformedDocument)


def test_an_apply_entry_without_an_entry_is_malformed() -> None:
    document = json.loads(_document())
    del document["entry"]

    assert "needs entry" in _reason(json.dumps(document))


def test_an_entry_the_add_rule_refuses_is_refused_here_too() -> None:
    bad = {**_ENTRY, "params": {"lower": "x" * 5000}}

    assert isinstance(parse_command(_document(entry=bad)), MalformedDocument)


@pytest.mark.parametrize(
    "overrides",
    [
        {"bot_id": PLAN_SUBJECT},
        {"desired_state": "running"},
        {"confirmed_venue": "spot_testnet"},
    ],
    ids=["names-no-bot", "carries-a-wish", "asks-venue"],
)
def test_an_unplan_names_a_bot_and_carries_nothing_else(
    overrides: dict[str, object],
) -> None:
    document = json.loads(_document(action="unplan", bot_id="44wa1x"))
    del document["entry"]
    document.update(overrides)

    assert isinstance(parse_command(json.dumps(document)), MalformedDocument)


@pytest.mark.parametrize("action", ["stop", "delete"])
def test_desired_state_belongs_to_an_apply_entry_alone(action: str) -> None:
    document = json.loads(_document(action=action, bot_id="44wa1x"))
    del document["entry"]

    assert "desired_state" in _reason(json.dumps(document))
