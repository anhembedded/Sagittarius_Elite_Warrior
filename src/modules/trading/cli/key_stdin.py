"""`BOT-200` — where `key check` gets a key: its standard input, nowhere else.

@details A key in an argument is in the process list and the shell's history; one in
an environment variable is in `/proc/<pid>/environ` and in what a child inherits; one
in a file argument is a file somebody must delete. Standard input is none of these, so
the command offers no other way in. Two lines, the key then the secret; on a terminal
the person is asked for each with the echo off.

Only the line ending is dropped. A space or any other stray character stays, so the
check refuses it and says so, instead of a stripped value passing here and failing at
the exchange.
"""

from __future__ import annotations

import getpass
from collections.abc import Callable
from typing import TextIO

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)

type _Ask = Callable[[str], str]


def read_key_from(stdin: TextIO, ask: _Ask = getpass.getpass) -> ExchangeCredentials:
    """The key and the secret `stdin` holds; an empty value for a line it lacks.

    @param ask Prompts with the echo off; used only when `stdin` is a terminal.
    """
    if stdin.isatty():
        return ExchangeCredentials(ask("API key: "), ask("API secret: "))
    return ExchangeCredentials(_line(stdin), _line(stdin))


def _line(stdin: TextIO) -> str:
    return stdin.readline().rstrip("\r\n")
