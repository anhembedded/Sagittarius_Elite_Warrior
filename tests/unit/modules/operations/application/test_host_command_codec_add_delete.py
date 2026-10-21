"""`EPIC-045` - the wire form of an add's entry and of a delete."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    LOSS_CAP_SUBJECT,
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    MalformedDocument,
    encode_command,
    parse_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    MAX_COMMAND_BYTES,
    HostCommand,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
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


# ---- EPIC-045: an add's entry and a delete -----------------------------------------------------

_ENTRY = {
    "name": "sol grid",
    "kind": "grid",
    "venue": "spot_testnet",
    "symbol": "SOLUSDT",
    "params": {"lower": "80", "upper": "120"},
}


def _add_document(**overrides: object) -> str:
    document: dict[str, object] = {
        "action": "add",
        "bot_id": ADD_SUBJECT,
        "entry": dict(_ENTRY),
        **overrides,
    }
    return _document(**document)


def _an_add(entry: NewBotEntry) -> HostCommand:
    return command(action=HostControlAction.ADD, bot_id=ADD_SUBJECT, entry=entry)


def test_an_add_survives_the_round_trip_with_its_entry() -> None:
    sent = _an_add(
        NewBotEntry(
            "sol grid",
            "grid",
            "spot_testnet",
            "SOLUSDT",
            (ParameterSetting("lower", "80"), ParameterSetting("upper", "120")),
        )
    )

    parsed = parse_command(encode_command(sent))

    assert parsed == sent
    assert not isinstance(parsed, MalformedDocument)
    assert parsed.entry is not None
    assert [(p.key, p.value) for p in parsed.entry.params] == [
        ("lower", "80"),
        ("upper", "120"),
    ]


def test_every_other_action_is_still_the_document_an_older_host_reads_after_epic_045() -> (
    None
):
    for action in HostControlAction:
        if action in (HostControlAction.ADD, HostControlAction.EDIT):
            continue
        sent = command(
            action=action,
            bot_id=LOSS_CAP_SUBJECT
            if action is HostControlAction.ACKNOWLEDGE_LOSS_CAP
            else BOT,
        )
        assert "entry" not in json.loads(encode_command(sent))


def test_an_add_adds_a_new_key_and_a_new_word_so_an_older_host_refuses_it_unread() -> (
    None
):
    document = json.loads(
        encode_command(_an_add(NewBotEntry("a", "grid", "spot_testnet", "SOLUSDT")))
    )

    assert document["action"] == "add"
    assert set(document) - {
        "schema",
        "command_id",
        "action",
        "bot_id",
        "confirmed_venue",
        "issued_at",
    } == {"entry"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"entry": None},
        {"entry": "grid"},
        {"entry": {**_ENTRY, "extra": "x"}},
        {"entry": {k: v for k, v in _ENTRY.items() if k != "symbol"}},
        {"entry": {**_ENTRY, "name": " sol"}},
        {"entry": {**_ENTRY, "name": "sol (grid)"}},
        {"entry": {**_ENTRY, "name": "n" * 65}},
        {"entry": {**_ENTRY, "kind": "Grid"}},
        {"entry": {**_ENTRY, "venue": "spot testnet"}},
        {"entry": {**_ENTRY, "symbol": "solusdt"}},
        {"entry": {**_ENTRY, "params": []}},
        {"entry": {**_ENTRY, "params": {"lower": 80}}},
        {"entry": {**_ENTRY, "params": {"Lower": "80"}}},
        {"entry": {**_ENTRY, "params": {"lower": "8 0"}}},
        {
            "entry": {
                **_ENTRY,
                "params": {f"k{i}": "1" for i in range(MAX_SETTINGS_PER_EDIT + 1)},
            }
        },
        {"bot_id": "44wa1x"},
        {"confirmed_venue": "spot_mainnet"},
        {"close_position": True},
        {"set": {"lower": "1"}},
    ],
    ids=[
        "null-entry",
        "text-entry",
        "extra-key",
        "missing-key",
        "name-leading-space",
        "name-bracket",
        "name-too-long",
        "kind-capital",
        "venue-space",
        "symbol-lower",
        "params-list",
        "params-number",
        "param-key-capital",
        "param-value-space",
        "too-many-params",
        "names-a-bot",
        "names-a-venue",
        "closes",
        "sets",
    ],
)
def test_an_add_document_that_is_not_exactly_one_is_malformed(
    overrides: dict[str, object],
) -> None:
    assert isinstance(parse_command(_add_document(**overrides)), MalformedDocument)


def test_an_add_without_an_entry_is_malformed() -> None:
    document = json.loads(_add_document())
    del document["entry"]

    assert isinstance(parse_command(json.dumps(document)), MalformedDocument)


@pytest.mark.parametrize(
    "action", ["stop", "pause", "resume", "start", "edit", "delete"]
)
def test_an_entry_belongs_to_an_add_alone(action: str) -> None:
    extra: dict[str, object] = {"set": {"lower": "1"}} if action == "edit" else {}
    parsed = parse_command(_document(action=action, entry=dict(_ENTRY), **extra))

    assert isinstance(parsed, MalformedDocument)
    assert "entry" in parsed.reason


def test_the_new_bot_subject_is_not_a_bot_id_for_any_other_action() -> None:
    assert isinstance(parse_command(_document(bot_id=ADD_SUBJECT)), MalformedDocument)


def test_a_malformed_entry_is_refused_without_repeating_its_values() -> None:
    parsed = parse_command(
        _add_document(entry={**_ENTRY, "params": {"lower": "pa ss word"}})
    )

    assert isinstance(parsed, MalformedDocument)
    assert "pa ss" not in parsed.reason


def test_the_largest_add_fits_the_commands_size_limit() -> None:
    biggest = _an_add(
        NewBotEntry(
            "n" * 64,
            "k" * 32,
            "v" * 32,
            "S" * 32,
            tuple(
                ParameterSetting(f"k{i:0>31}", "9" * 64)
                for i in range(MAX_SETTINGS_PER_EDIT)
            ),
        )
    )

    text = encode_command(biggest)

    assert len(text.encode("utf-8")) < MAX_COMMAND_BYTES
    assert parse_command(text) == biggest


def test_a_delete_survives_the_round_trip_and_asks_no_venue() -> None:
    sent = command(action=HostControlAction.DELETE, bot_id="abc123")

    assert parse_command(encode_command(sent)) == sent
    assert isinstance(
        parse_command(_document(action="delete", confirmed_venue="spot_mainnet")),
        MalformedDocument,
    )
    assert isinstance(
        parse_command(_document(action="delete", set={"lower": "1"})),
        MalformedDocument,
    )
