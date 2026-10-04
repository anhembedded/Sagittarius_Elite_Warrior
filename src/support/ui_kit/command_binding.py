"""How a presenter performs the commands its module contributed (`EPIC-033D`).

A module declares a command in `contribute()` (`CommandContribution`), before
any presenter exists. The window builds every mode at start, and as each
presenter is built it is handed the binder. A presenter that implements
`IBindsCommands` binds a handler, and the state that enables its command, for
each command it performs. A contributed command that nothing binds stays
disabled, and the Engine logs it once at the end of boot.

The binder is the Engine's `ActionRegistry`, which has exactly this `bind`.

Both are `Protocol`s: the binder is third-party (reason (c)), and the
implementers of `IBindsCommands` are presenters, `QObject`s (reason (a))
(`architecture-rule.md` §2.1). They live here, not in `core/contracts`,
because their signatures name Qt's `SignalInstance`, which only presentation
may know.

Plausible extensions, each a local change: a checked state bound from a
signal (already a `bind` argument); a presenter that binds a command only in
developer mode (a branch in its own `bind_commands`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PySide6.QtCore import SignalInstance


class ICommandBinder(Protocol):
    """Connects one contributed command to what performs it."""

    def bind(
        self,
        action_id: str,
        handler: Callable[[bool], None],
        *,
        enabled: SignalInstance | None = None,
        checked: SignalInstance | None = None,
        initially_enabled: bool = True,
    ) -> None:
        """`handler` gets the checked state (`False` for a plain command).
        `enabled` and `checked` keep the action in step with the presenter;
        `initially_enabled` holds until `enabled` first fires."""
        ...


@runtime_checkable
class IBindsCommands(Protocol):
    """A presenter that performs commands its module contributed."""

    def bind_commands(self, binder: ICommandBinder) -> None: ...
