"""Where a module declares the interactive-shell commands it owns.

`EPIC-025` PR 1.3c-5. The shell's dispatch table was a dict literal inside
`interactive_shell.py`:

    self.handlers = {"sync": SyncCliHandler, "stream": StreamCliHandler, ...}

so the shell named classes that live inside modules, and the boundary allowlist
carried two entries for it. `interactive_shell.py` could not simply move into
`shell/` either: PR 1.1b tried, measured it, and reverted — the move traded
those two entries for two new lines in the shell's shrink-only legacy-import
baseline, which is a ratchet growing so another can shrink.

The inversion is the same one `IContributionRegistry` already makes for panels:
**the module declares, the shell collects.** The shell names no module class,
the module names no shell class, and adding a command touches one file — the
module that owns it.

`cli_commands.json` still declares each command's *arguments*, and still does
the parsing (PR 0.4a-2 inverted that separately, see `ICliCommandHandler`). A
declaration here says who runs a command, not what its arguments are; a name
declared here with no entry in that file would parse as taking none, which the
shell reports rather than crashing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)


@dataclass(frozen=True, slots=True)
class CliCommandDescriptor:
    """One command a module owns, ready for the shell's table."""

    #: The word the user types, exactly as `cli_commands.json` spells it —
    #: `"exchange-status"`, hyphen and all.
    name: str
    #: The handler class, not an instance: `ICliCommandHandler.handle` is a
    #: `staticmethod`, so there is nothing to construct and no per-command
    #: state for the shell to own.
    handler: type[ICliCommandHandler]
    #: Which module declared it, so a clash names both sides.
    contributor_id: str


class ICliRegistry(ABC):
    """What a module sees of the shell's command table: one call, no reads."""

    @abstractmethod
    def declare(self, descriptor: CliCommandDescriptor) -> None:
        """Claim `descriptor.name` for this module's handler.

        Two modules claiming one name is a programming error, not a runtime
        condition to resolve: the shell raises rather than letting whichever
        registered last quietly win.
        """


class ICliCommandTable(ABC):
    """What the **prompt** sees: the finished table, and no way to add to it.

    Two ports over one object, deliberately. A module must not be able to read
    what other modules declared — that is how a command starts depending on
    another context's presence — and the prompt must not be able to declare,
    because then the collection would have two sources. One implementation
    satisfies both (`shell/cli_registry.py`), and each side names only the half
    it is allowed to use. `ITradingSessionFactory` and `ITradingSessionClient`
    share a file for the same reason: two roles of one collaboration.
    """

    @abstractmethod
    def handlers(self) -> dict[str, type[ICliCommandHandler]]:
        """The dispatch table, keyed by the word the user types, in a stable
        order so `help` reads the same on every run."""
