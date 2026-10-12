"""A word the command line accepts that starts the application in a mode, not a report command.

Capability: Start the application in a mode from one command-line word
    Also: gui, shell, launcher verb, bare main.py, entry point, run mode, subcommand that opens a window
    Use: LauncherVerb, add_launcher_verbs
    User: src/main.py
    Status: stable

`EPIC-038B`, decision D8. `gui` opens the desktop window, `shell` the
interactive prompt, and (`EPIC-038D`) `run` will serve until told to stop.
None of them is a `cli_commands.json` entry: that file is the REPL's `help`
and the headless parser's report commands, and a verb that opens a window has
no business in either list. A verb is declared by the entry point as data
(this class), the parser lists it in `--help` and accepts only its flags; what
the word *starts* stays in the entry point, because that is application code
(which window, which prompt) and this package knows none.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LauncherVerb:
    name: str
    help: str
    #: Optional flags the verb accepts and the mode it starts reads itself
    #: (`--dev`); the parser only has to let them through.
    flags: tuple[str, ...] = ()


def add_launcher_verbs(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    verbs: tuple[LauncherVerb, ...],
) -> None:
    """List each verb in `--help`, accepting only its declared flags."""
    for verb in verbs:
        parser = subparsers.add_parser(verb.name, help=verb.help)
        for flag in verb.flags:
            parser.add_argument(flag, action="store_true")
