"""`EPIC-038J` - the wire form of a command: strict on the way in, exact on the way out."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
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


def test_a_start_survives_the_round_trip() -> None:
    sent = command(action=HostControlAction.START, confirmed_venue="futures_mainnet")

    assert parse_command(encode_command(sent)) == sent


def test_the_new_action_is_a_new_word_not_a_new_key() -> None:
    """`EPIC-038K`: an older host reads the same keys and a word it does not know, so it refuses
    the document as malformed (REJECTED, audited, nothing executed) instead of misreading it."""
    document = json.loads(encode_command(command(action=HostControlAction.START)))

    assert set(document) == {
        "schema",
        "command_id",
        "action",
        "bot_id",
        "confirmed_venue",
        "issued_at",
    }
    assert document["action"] == "start"


def test_delete_is_not_an_action_the_host_knows() -> None:
    """The owner dropped `bot delete` from `EPIC-038K` (2026-10-17): no word for it on the wire."""
    parsed = parse_command(_document(action="delete"))

    assert isinstance(parsed, MalformedDocument)
    assert "action" in parsed.reason


def test_the_refusal_of_an_unknown_action_lists_every_action_the_host_knows() -> None:
    parsed = parse_command(_document(action="restart"))

    assert isinstance(parsed, MalformedDocument)
    for action in HostControlAction:
        assert action.value in parsed.reason


# ---- EPIC-038L: an edit's settings -----------------------------------------------------------


def _edit_document(**overrides: object) -> str:
    return _document(
        **{"action": "edit", "set": {"lower": "81000", "upper": "90000"}, **overrides}
    )


def _an_edit(*settings: ParameterSetting) -> HostCommand:
    return command(action=HostControlAction.EDIT, settings=settings)


def test_an_edit_survives_the_round_trip_with_its_settings_in_order_of_the_wire() -> (
    None
):
    sent = _an_edit(
        ParameterSetting("lower", "81000"), ParameterSetting("upper", "90000")
    )

    parsed = parse_command(encode_command(sent))

    assert isinstance(parsed, HostCommand)
    assert {s.key: s.value for s in parsed.settings} == {
        "lower": "81000",
        "upper": "90000",
    }
    assert parsed.action is HostControlAction.EDIT and parsed.confirmed_venue is None


def test_every_other_action_is_still_the_document_an_older_host_reads() -> None:
    """`set` is written only for an edit: a stop, pause, resume or start adds no key."""
    for action in (
        HostControlAction.STOP,
        HostControlAction.PAUSE,
        HostControlAction.RESUME,
        HostControlAction.START,
    ):
        assert "set" not in json.loads(encode_command(command(action=action)))


def test_an_edit_adds_a_new_key_and_a_new_word_so_an_older_host_refuses_it_unread() -> (
    None
):
    """What an older host (keys `schema` ... `close_position`, actions stop|pause|resume|start) does:
    it checks the keys first and finds `set` unknown, so the document is MALFORMED, REJECTED to the
    operator, audited and executed never. Simulated with that host's closed key set."""
    older_keys = {
        "schema",
        "command_id",
        "action",
        "bot_id",
        "confirmed_venue",
        "issued_at",
        "close_position",
    }
    document = json.loads(encode_command(_an_edit(ParameterSetting("lower", "81000"))))

    assert set(document) - older_keys == {"set"}
    assert document["action"] == "edit"


@pytest.mark.parametrize(
    ("text", "why"),
    [
        (_edit_document(set=None), "set"),
        (_edit_document(set="lower=1"), "set"),
        (_edit_document(set=["lower"]), "set"),
        (_edit_document(set={}), "set"),
        (_edit_document(set={"lower": 81000}), "text"),
        (_edit_document(set={"lower": ""}), "lower"),
        (_edit_document(set={"Lower": "1"}), "key"),
        (_edit_document(set={"lower;rm": "1"}), "key"),
        (_edit_document(set={"": "1"}), "key"),
        (_edit_document(set={"lower": "81 000"}), "lower"),
        (_edit_document(set={"lower": "1" * 65}), "lower"),
        (_edit_document(set={"lower": '"1"'}), "lower"),
        (_edit_document(set={"k" * 33: "1"}), "key"),
        (
            _edit_document(
                set={f"p{i}": "1" for i in range(MAX_SETTINGS_PER_EDIT + 1)}
            ),
            "set",
        ),
        (_document(action="edit"), "needs set"),
        (_edit_document(confirmed_venue="spot_mainnet"), "no venue"),
        (_edit_document(close_position=True), "close_position"),
        (_document(action="start", set={"lower": "1"}), "belongs to an edit"),
        (_document(action="stop", set={"lower": "1"}), "belongs to an edit"),
    ],
)
def test_an_edit_document_that_is_not_exactly_one_is_malformed(
    text: str, why: str
) -> None:
    parsed = parse_command(text)

    assert isinstance(parsed, MalformedDocument)
    assert why in parsed.reason
    assert parsed.command_id == ID_A


def test_a_malformed_setting_is_refused_without_repeating_its_value() -> None:
    parsed = parse_command(_edit_document(set={"lower": "pa ss"}))

    assert isinstance(parsed, MalformedDocument)
    assert "pa ss" not in parsed.reason


def test_the_largest_edit_fits_the_commands_size_limit() -> None:
    biggest = _an_edit(
        *(
            ParameterSetting(f"k{i:0>31}", "9" * 64)
            for i in range(MAX_SETTINGS_PER_EDIT)
        )
    )

    text = encode_command(biggest)

    assert len(text.encode("utf-8")) < MAX_COMMAND_BYTES
    assert parse_command(text) == biggest
