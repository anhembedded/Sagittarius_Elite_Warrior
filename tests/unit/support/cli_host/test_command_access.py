"""Which commands may run without being the writable copy (`EPIC-038C`)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.support.cli_host.command_access import (
    command_is_read_only,
    command_keeps_log_off_console,
    command_owns_its_lifecycle,
    command_requires_writable_instance,
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
                "apply": {"read_only_when": "dry_run"},
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
        (_args(command="bot", action="apply", dry_run=True), True),
        (_args(command="bot", action="apply", dry_run=False), False),
        (_args(command="bot", action="apply"), False),
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
    # Reads the bots and writes a file the operator named; touches no bot.
    ("bot", "export"),
    # `EPIC-038J` - write a command file for the running host and wait for its answer; this
    # process changes no bot, and a lock it took would be the one the host holds.
    ("bot", "stop"),
    ("bot", "pause"),
    ("bot", "resume"),
    ("bot", "start"),
    ("preflight", None),
    ("exchange-status", None),
    ("order-preview", None),
    # Always a VALIDATE_ONLY client, which a read-only copy lets through.
    ("order-dry-run", None),
    # `EPIC-036G` - sends a test message through each channel; writes no outbox.
    ("alert", "test"),
}
#: Writable on purpose (`EPIC-038C` note 15): they write market data, open the
#: live feed, or place real orders, which a read-only copy refuses.
_WRITABLE = {
    ("sync", None),
    ("stream", "start"),
    ("stream", "stop"),
    ("trade-once", None),
    # Read-only with `--dry-run` (`read_only_when`), the writable copy otherwise.
    ("bot", "apply"),
    # The writable copy by definition: it trades, and refuses to start without the lock.
    ("run", None),
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


_HOSTS = {
    "run": {"requires_writable": True, "owns_lifecycle": True},
    "status": {"read_only": True},
    "sync": {},
    "bot": {
        "subparsers": {
            "dest": "action",
            "commands": {"start": {"requires_writable": True}, "list": {}},
        }
    },
}


@pytest.mark.parametrize(
    ("args", "writable", "owns"),
    [
        (_args(command="run"), True, True),
        (_args(command="status"), False, False),
        (_args(command="sync"), False, False),
        (_args(command="unknown"), False, False),
        (_args(command="bot", action="start"), True, False),
        (_args(command="bot", action="list"), False, False),
    ],
)
def test_a_command_declares_that_it_needs_the_lock_and_that_it_owns_its_lifecycle(
    args: argparse.Namespace, writable: bool, owns: bool
) -> None:
    assert command_requires_writable_instance(_HOSTS, args) is writable
    assert command_owns_its_lifecycle(_HOSTS, args) is owns


def test_only_run_requires_the_lock_and_owns_its_lifecycle_in_the_shipped_table() -> (
    None
):
    shipped = _shipped()
    leaves = _every_shipped_leaf()

    requiring = {
        leaf
        for leaf in leaves
        if command_requires_writable_instance(
            shipped, _args(command=leaf[0], action=leaf[1])
        )
    }
    owning = {
        leaf
        for leaf in leaves
        if command_owns_its_lifecycle(shipped, _args(command=leaf[0], action=leaf[1]))
    }

    assert requiring == {("run", None)}
    assert owning == {("run", None)}


def test_apply_is_read_only_exactly_when_it_is_a_dry_run_in_the_shipped_table() -> None:
    shipped = _shipped()

    assert command_is_read_only(
        shipped, _args(command="bot", action="apply", dry_run=True)
    )
    assert not command_is_read_only(
        shipped, _args(command="bot", action="apply", dry_run=False)
    )


_LOG_TABLE = {
    "reads": {"read_only": True},
    "writes_once": {"short_lived": True},
    "serves": {"keeps_console_log": True},
    "reads_but_keeps": {"read_only": True, "keeps_console_log": True},
    "undeclared": {},
    "bot": {
        "subparsers": {
            "dest": "action",
            "commands": {
                "apply": {"read_only_when": "dry_run", "short_lived": True},
                "list": {"read_only": True},
                "watch": {"keeps_console_log": True},
            },
        }
    },
}


@pytest.mark.parametrize(
    ("args", "quiet"),
    [
        (_args(command="reads"), True),
        (_args(command="writes_once"), True),
        (_args(command="serves"), False),
        (_args(command="reads_but_keeps"), False),
        (_args(command="undeclared"), False),
        (_args(command="bot", action="apply", dry_run=False), True),
        (_args(command="bot", action="apply", dry_run=True), True),
        (_args(command="bot", action="list"), True),
        (_args(command="bot", action="watch"), False),
    ],
)
def test_a_command_keeps_its_log_off_the_console_when_it_reads_or_is_short_lived(
    args: argparse.Namespace, quiet: bool
) -> None:
    assert command_keeps_log_off_console(_LOG_TABLE, args) is quiet
