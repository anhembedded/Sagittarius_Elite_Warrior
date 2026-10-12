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


def test_the_shipped_commands_that_only_read_say_so() -> None:
    shipped = json.loads(
        (
            Path(__file__).resolve().parents[4] / "src/config/cli_commands.json"
        ).read_text(encoding="utf-8")
    )["CLI_COMMANDS"]

    read_only = {
        ("status", None): command_is_read_only(shipped, _args(command="status")),
        ("bot", "list"): command_is_read_only(
            shipped, _args(command="bot", action="list")
        ),
        ("bot", "show"): command_is_read_only(
            shipped, _args(command="bot", action="show")
        ),
    }
    assert all(read_only.values()), read_only
    for writer in ("sync", "stream", "trade-once", "order-dry-run"):
        assert (
            command_is_read_only(shipped, _args(command=writer, action=None)) is False
        )
