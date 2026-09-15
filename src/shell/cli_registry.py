"""The shell's side of the CLI-command mechanism (`EPIC-025` PR 1.3c-5).

`ICliRegistry` is what a module sees: one call that takes a descriptor and
gives nothing back. This class adds the half only the shell needs — reading
the table, in a deterministic order — and the validation that makes a mistake
fail while the stack still names the module that made it.

**A name may be claimed once.** Unlike a panel, where two modules contributing
to the same surface is the normal case and order is a sort key, a command word
is an identity: `sync` can only mean one thing at the prompt. The second claim
raises `ContributionError` naming both modules, which happens at boot rather
than on the first `sync` a user types.

The shape follows `ContributionRegistry` deliberately — same file layout, same
"module-facing side / shell-facing side" split, same error type — so a reader
who has understood one has understood both (`onb` §12.5: follow the proven
pattern rather than inventing a second one).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    CliCommandDescriptor,
    ICliCommandTable,
    ICliRegistry,
)

logger = logging.getLogger("App.Shell.CliRegistry")


class CliRegistry(ICliRegistry, ICliCommandTable):
    """Collects the commands every module owns, and hands the shell a table."""

    def __init__(self) -> None:
        self._commands: dict[str, CliCommandDescriptor] = {}

    # -- the module-facing side (ICliRegistry) -----------------------------

    def declare(self, descriptor: CliCommandDescriptor) -> None:
        claimed = self._commands.get(descriptor.name)
        if claimed is not None:
            raise ContributionError(
                f"{descriptor.contributor_id!r} declared the CLI command "
                f"{descriptor.name!r}, which {claimed.contributor_id!r} already "
                "owns. A command word is an identity, not a sort key: rename "
                "one of them."
            )
        self._commands[descriptor.name] = descriptor
        logger.debug(
            "CLI command %r declared by %r -> %s.",
            descriptor.name,
            descriptor.contributor_id,
            descriptor.handler.__name__,
        )

    # -- the prompt-facing side (ICliCommandTable) -------------------------

    def handlers(self) -> dict[str, type[ICliCommandHandler]]:
        """The dispatch table, keyed by the word the user types.

        Sorted by name so the shell's `help` output and any log of what was
        collected read the same on every run — the same reason
        `ContributionRegistry` sorts rather than trusting insertion order.
        """
        return {name: self._commands[name].handler for name in sorted(self._commands)}

    def owner_of(self, name: str) -> str | None:
        """Which module declared `name`, for a diagnostic. `None` if nobody
        did — which is what the shell reports for an unknown command."""
        claimed = self._commands.get(name)
        return None if claimed is None else claimed.contributor_id
