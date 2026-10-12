"""Whether a command may change anything, read from its declaration.

Capability: Decide before the app boots whether a command needs the writable copy of the data root
    Also: read-only command, status, bot list, take the lock, writable instance, command changes nothing, read_only in cli_commands.json
    Use: command_is_read_only
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

@par Extension cases
  · a new read-only command or verb - `"read_only": true` on its entry; this
    function and the entry point do not change;
  · a mutating verb under a read-only command - leave the key off the verb.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

#: The key in a command's (or sub-command's) `cli_commands.json` entry.
READ_ONLY_KEY = "read_only"


def command_is_read_only(commands: Mapping[str, Any], args: argparse.Namespace) -> bool:
    """True when the entry for the parsed command, or for its sub-command, says so.

    The sub-command's own entry wins over its parent's: `bot` may hold both a
    reading verb and, later, a writing one.
    """
    entry = commands.get(args.command)
    if not isinstance(entry, Mapping):
        return False
    subparsers = entry.get("subparsers")
    if isinstance(subparsers, Mapping):
        chosen = getattr(args, str(subparsers.get("dest", "subcommand")), None)
        sub_entry = subparsers.get("commands", {}).get(chosen)
        if isinstance(sub_entry, Mapping) and READ_ONLY_KEY in sub_entry:
            return bool(sub_entry[READ_ONLY_KEY])
    return bool(entry.get(READ_ONLY_KEY, False))
