"""`BOT-186` - a command cannot slip into a console behaviour nobody chose.

`cli_commands.json` is where a command says whether it only reads, is a short-lived
writer, or keeps its console log (`run`'s is the supervisor's, `sync`'s is its progress,
`stream start` runs until told to stop). The routing reads that declaration
(`command_keeps_log_off_console`), so a new command that said nothing would silently get
the default of the day. This reads the real file and fails until it chooses.

Retire when: the registry is derived from the modules' `declare_cli` and the table is
checked where the descriptor is built.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.shell.app_config import CLI_COMMANDS_FILE
from Sagittarius_Elite_Warrior.src.support.cli_host.command_access import (
    KEEPS_CONSOLE_LOG_KEY,
    READ_ONLY_KEY,
    READ_ONLY_WHEN_KEY,
    SHORT_LIVED_KEY,
    command_keeps_log_off_console,
)

#: The declarations that put a command on the quiet side, and the one that opts out.
_QUIET_SIDES = (READ_ONLY_KEY, READ_ONLY_WHEN_KEY, SHORT_LIVED_KEY)


def _groups(
    commands: Mapping[str, Any], prefix: tuple[str, ...] = ()
) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Every entry that only holds verbs, with its path."""
    for name, entry in commands.items():
        verbs = entry.get("subparsers", {}).get("commands")
        if verbs:
            yield " ".join((*prefix, name)), entry
            yield from _groups(verbs, (*prefix, name))


def _leaves(
    commands: Mapping[str, Any], prefix: tuple[str, ...] = ()
) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Every command that is run (not a group of verbs), with its path."""
    for name, entry in commands.items():
        verbs = entry.get("subparsers", {}).get("commands")
        if verbs:
            yield from _leaves(verbs, (*prefix, name))
        else:
            yield " ".join((*prefix, name)), entry


_COMMANDS: Mapping[str, Any] = json.loads(
    CLI_COMMANDS_FILE.read_text(encoding="utf-8")
)["CLI_COMMANDS"]
_LEAVES = dict(_leaves(_COMMANDS))
_GROUPS = dict(_groups(_COMMANDS))


def test_the_registry_has_commands_to_check() -> None:
    assert "run" in _LEAVES
    assert "bot apply" in _LEAVES


@pytest.mark.parametrize("path", sorted(_LEAVES))
def test_a_command_says_which_side_of_the_console_it_is_on(path: str) -> None:
    entry = _LEAVES[path]
    sides = [key for key in (*_QUIET_SIDES, KEEPS_CONSOLE_LOG_KEY) if entry.get(key)]

    assert sides, (
        f"`{path}` declares neither a quiet side ({', '.join(_QUIET_SIDES)}) nor "
        f"`{KEEPS_CONSOLE_LOG_KEY}`: say where its log goes in cli_commands.json "
        "(`command_access.py`, `BOT-186`)"
    )
    if entry.get(KEEPS_CONSOLE_LOG_KEY):
        assert sides == [KEEPS_CONSOLE_LOG_KEY], (
            f"`{path}` declares both sides: {sides}"
        )


def test_the_registry_has_a_group_of_verbs_to_check() -> None:
    assert "bot" in _GROUPS


@pytest.mark.parametrize("path", sorted(_GROUPS))
def test_a_group_of_verbs_declares_no_side_for_its_verbs_to_inherit(path: str) -> None:
    """A verb without its own key falls back to its group's (`_declared_value`), so a
    stray `keeps_console_log` on `bot` would make `bot list` noisy with every leaf
    still passing its own check."""
    stray = [
        key for key in (*_QUIET_SIDES, KEEPS_CONSOLE_LOG_KEY) if key in _GROUPS[path]
    ]

    assert not stray, f"`{path}` is a group: declare {stray} on each verb instead"


@pytest.mark.parametrize("path", sorted(_LEAVES))
def test_a_commands_effective_routing_is_what_it_declares(path: str) -> None:
    """The routing `main` acts on, for the real parsed shape of each leaf, matches the
    leaf's own declaration."""
    *group, verb = path.split(" ")
    namespace = {"command": group[0] if group else verb}
    if group:
        subparsers = _COMMANDS[group[0]]["subparsers"]
        namespace[subparsers.get("dest", "subcommand")] = verb
    entry = _LEAVES[path]
    args = argparse.Namespace(**namespace, dry_run=False)

    expected = not entry.get(KEEPS_CONSOLE_LOG_KEY) and bool(
        entry.get(READ_ONLY_KEY)
        or entry.get(READ_ONLY_WHEN_KEY)
        or entry.get(SHORT_LIVED_KEY)
    )
    # `bot apply --dry-run` and `bot apply` are both quiet, so `dry_run=False` is the
    # stricter of the two for a `read_only_when` verb: only `short_lived` carries it.
    assert command_keeps_log_off_console(_COMMANDS, args) is expected


@pytest.mark.parametrize(
    ("argv", "quiet"),
    [
        (["status"], True),
        (["bot", "list"], True),
        (["bot", "apply"], True),
        (["bot", "apply", "--dry-run"], True),
        (["trade-once"], False),
        (["run"], False),
        (["sync"], False),
        (["stream", "start"], False),
    ],
)
def test_the_commands_the_owner_named_are_on_the_side_the_owner_chose(
    argv: list[str], quiet: bool
) -> None:
    """`bot apply` is a short-lived writer (quiet). `trade-once` keeps its console log by the
    owner's decision (`--live` can trade real money and no local order journal exists);
    `run` keeps the log on stdout for journald and NSSM, `sync` and `stream start` keep it
    as their output."""
    args = argparse.Namespace(
        command=argv[0],
        **({"action": argv[1]} if len(argv) > 1 else {}),
        dry_run="--dry-run" in argv,
    )

    assert command_keeps_log_off_console(_COMMANDS, args) is quiet
