"""One interactive-shell command, implemented by the context that owns it.

`EPIC-018F` introduced this port to replace duck-typing: the shell's dispatch
table held plain classes with no declared shape, and `handler.handle(...)` was
"call it and hope".

**`EPIC-025` PR 0.4a-2 inverted who parses.** The signature was
`handle(arg_str: str, app)` — the shell re-joined the words it had just split,
and each handler split them again, built its own parser from config, and
repeated the same three `except` blocks. Two consequences, one cosmetic and one
structural:

- every new command copied ~15 lines of parsing before reaching its one real
  line of work;
- a handler had to import the parser builder to do its job, so a command owned
  by `market_data` could not live in `market_data` — it had to reach back into
  the legacy CLI package. That is an import pointing the wrong way, which the
  boundary guard refuses outright.

Now the **caller parses** and hands over an `argparse.Namespace`. This is the
shape every established tool uses for a plugin-contributed command — Django's
`BaseCommand` (`add_arguments(parser)` declares, `handle(**options)` receives),
Click and Typer (decorators declare, the framework parses and calls with
values), and argparse's own subparsers (`set_defaults(func=...)`, called with
the parsed namespace). None of them has the command parse its own raw string.

The argument *spec* still lives in `cli_commands.json`, so a command declares
its arguments as data and neither side hard-codes them.

Why this port is in `core/contracts/` rather than beside the shell's CLI: the
implementations belong to modules, and nothing may import the shell. Same
inversion as `IContributionRegistry` — the module implements, the shell
collects.
"""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagittarius_engine import App


class ICliCommandHandler(ABC):
    """One interactive-shell command (`sync`, `stream`, ...)."""

    @staticmethod
    @abstractmethod
    def handle(args: argparse.Namespace, app: App) -> None:
        """Run the command against already-parsed arguments.

        `args` carries exactly the arguments `cli_commands.json` declares for
        this command, with defaults applied. A handler must not parse, re-split
        or re-validate the raw line: by the time it is called, `-h` has been
        answered and a malformed line has been reported and rejected.

        Reporting failure is still the handler's job, because only it knows
        what went wrong: catch the domain's own errors and print something the
        user can act on rather than letting a traceback reach the prompt.
        """
