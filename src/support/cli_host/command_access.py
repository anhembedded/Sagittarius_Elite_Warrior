"""Whether a command may change anything, read from its declaration.

Capability: Decide before the app boots whether a command needs the writable copy of the data root
    Also: read-only command, status, bot list, take the lock, writable instance, command changes nothing, read_only in cli_commands.json
    Use: command_is_read_only, command_requires_writable_instance, command_owns_its_lifecycle, command_keeps_log_off_console
    User: src/main.py
    Status: stable

`EPIC-038C`. The first copy of the app on a data root is the writable one, and
its boot applies the restart rule to every saved bot (a RUNNING bot becomes
RECOVERING). A command that only reads - `status`, `bot list`, `bot show` -
must not be that copy: run on a quiet machine it would rewrite the bots' files,
and run beside a host it would ask the lock "who has you" by taking it.
So `cli_commands.json` says `"read_only": true` on the command, or on the
sub-command that reads, and the entry point asks here **before** it takes the
lock. Absent means writable: the safe direction, and the one every command that
existed before this field keeps.

@par Two more declarations (`EPIC-038D`)
  · `"requires_writable": true` - a command that is only meaningful as the copy that
    trades (`run`): when another copy holds the data root the entry point prints why,
    exits `3` and builds nothing, where every other writable command boots read-only;
  · `"owns_lifecycle": true` - a command that boots and stops the app itself (`run`
    must check the machine *before* the bots are restored and wait *between* boot and
    stop), so the entry point hands it the built, unbooted app and does neither.

@par A verb that reads only with a flag (`EPIC-038I`)
  · `"read_only_when": "dry_run"` - `bot apply --dry-run` is read-only, `bot apply` is not.

@par Where the log goes (`BOT-185`, `BOT-186`)
  A command that only reads shows its result and nothing else; so does a short-lived one that
  writes (`bot apply`): its log records go to a file (`shell/cli_log_routing.py`).
  The declaration is explicit, so a new command cannot slip into either behaviour unseen:
  · `"short_lived": true` - a one-shot command that may change something and ends by itself;
  · `"keeps_console_log": true` - a command whose log is its output or that runs until told to
    stop (`run`: the supervisor's journal; `sync`: its progress; `stream start`; `trade-once`: it can trade real money and keeps no local order journal);
  and every command that is not a group of verbs says one of the four sides (`read_only`,
  `read_only_when`, `short_lived`, `keeps_console_log`), which
  `tests/unit/support/cli_host/test_every_command_declares_where_its_log_goes.py` checks.

@par Extension cases
  · a new read-only command or verb - `"read_only": true` on its entry; this
    function and the entry point do not change;
  · a mutating verb under a read-only command - leave the key off the verb.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

#: The keys in a command's (or sub-command's) `cli_commands.json` entry.
READ_ONLY_KEY = "read_only"
READ_ONLY_WHEN_KEY = "read_only_when"
REQUIRES_WRITABLE_KEY = "requires_writable"
OWNS_LIFECYCLE_KEY = "owns_lifecycle"
SHORT_LIVED_KEY = "short_lived"
KEEPS_CONSOLE_LOG_KEY = "keeps_console_log"


def _declared_value(
    commands: Mapping[str, Any], args: argparse.Namespace, key: str
) -> object:
    """The raw value of `key` for the parsed command, or `None` when it is not declared.

    The sub-command's own entry wins over its parent's: `bot` may hold both a
    reading verb and, later, a writing one.
    """
    entry = commands.get(args.command)
    if not isinstance(entry, Mapping):
        return None
    subparsers = entry.get("subparsers")
    if isinstance(subparsers, Mapping):
        chosen = getattr(args, str(subparsers.get("dest", "subcommand")), None)
        sub_entry = subparsers.get("commands", {}).get(chosen)
        if isinstance(sub_entry, Mapping) and key in sub_entry:
            return sub_entry[key]
    return entry.get(key)


def _declared(commands: Mapping[str, Any], args: argparse.Namespace, key: str) -> bool:
    """The truth of `key` for the parsed command; absent means `False`."""
    return bool(_declared_value(commands, args, key))


def command_is_read_only(commands: Mapping[str, Any], args: argparse.Namespace) -> bool:
    """True when the entry for the parsed command, or for its sub-command, says so.

    `"read_only_when": "<flag>"` (`EPIC-038I`) says so only when that parsed flag is on:
    `bot apply --dry-run` reads and prints a diff, `bot apply` changes bots, and the
    entry point must know which before it takes the lock."""
    if _declared(commands, args, READ_ONLY_KEY):
        return True
    flag = _declared_value(commands, args, READ_ONLY_WHEN_KEY)
    return isinstance(flag, str) and bool(getattr(args, flag, False))


def command_requires_writable_instance(
    commands: Mapping[str, Any], args: argparse.Namespace
) -> bool:
    """True for a command that must not run as a read-only copy (it exits 3 instead)."""
    return _declared(commands, args, REQUIRES_WRITABLE_KEY)


def command_owns_its_lifecycle(
    commands: Mapping[str, Any], args: argparse.Namespace
) -> bool:
    """True for a command that boots and stops the application itself."""
    return _declared(commands, args, OWNS_LIFECYCLE_KEY)


def command_keeps_log_off_console(
    commands: Mapping[str, Any], args: argparse.Namespace
) -> bool:
    """True for a command whose console shows its result only: one that reads, or a
    short-lived one that writes. `keeps_console_log` wins over both."""
    if _declared(commands, args, KEEPS_CONSOLE_LOG_KEY):
        return False
    return command_is_read_only(commands, args) or _declared(
        commands, args, SHORT_LIVED_KEY
    )
