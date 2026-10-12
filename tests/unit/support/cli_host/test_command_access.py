"""Which commands may run without being the writable copy (`EPIC-038C`)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.support.cli_host.command_access import (
    command_is_read_only,
)

_COMMANDS = {
    "sync": {"args": []},
    "status": {"read_only": True},
    "bot": {
        "subparsers": {
            "dest": "action",
            "commands": {
                "list": {"read_only": True},
                "show": {"read_only": True},
                "start": {},
            },
        }
    },
    "mixed": {
        "read_only": True,
        "subparsers": {"dest": "verb", "commands": {"write": {"read_only": False}}},
    },
}


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**values)


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (_args(command="status"), True),
        (_args(command="sync"), False),
        (_args(command="unknown"), False),
        (_args(command="bot", action="list"), True),
        (_args(command="bot", action="show"), True),
        (_args(command="bot", action="start"), False),
        (_args(command="mixed", verb="write"), False),
        (_args(command="mixed", verb="other"), True),
    ],
)
def test_the_declaration_decides(args: argparse.Namespace, expected: bool) -> None:
    assert command_is_read_only(_COMMANDS, args) is expected


_READ_ONLY = {
    ("status", None),
    ("bot", "list"),
    ("bot", "show"),
    ("preflight", None),
    ("exchange-status", None),
    ("order-preview", None),
}
#: Writable on purpose (`EPIC-038C` note 15): they write market data, open the
#: live feed, or go through order submission, which a read-only copy refuses.
_WRITABLE = {
    ("sync", None),
    ("stream", "start"),
    ("stream", "stop"),
    ("order-dry-run", None),
    ("trade-once", None),
}


def _shipped() -> dict[str, dict[str, object]]:
    path = Path(__file__).resolve().parents[4] / "src/config/cli_commands.json"
    return json.loads(path.read_text(encoding="utf-8"))["CLI_COMMANDS"]


def _every_shipped_leaf() -> set[tuple[str, str | None]]:
    leaves: set[tuple[str, str | None]] = set()
    for name, entry in _shipped().items():
        subparsers = entry.get("subparsers")
        if isinstance(subparsers, dict):
            leaves |= {(name, verb) for verb in subparsers["commands"]}
        else:
            leaves.add((name, None))
    return leaves


def test_every_shipped_command_has_a_recorded_read_only_decision() -> None:
    """A new command in `cli_commands.json` fails here until someone decides
    whether it only reads - the decision `preflight` was missing."""
    assert _every_shipped_leaf() == _READ_ONLY | _WRITABLE


def test_the_shipped_commands_say_what_was_decided() -> None:
    shipped = _shipped()
    for command, verb in sorted(_READ_ONLY | _WRITABLE, key=str):
        args = _args(command=command, action=verb)
        assert command_is_read_only(shipped, args) is ((command, verb) in _READ_ONLY), (
            command,
            verb,
        )
