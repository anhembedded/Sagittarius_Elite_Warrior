"""A presenter that performs commands its module contributed (`EPIC-033D`).

A module declares its commands in `contribute()` (`CommandContribution`),
before any presenter exists. `MainWindow` builds every mode at start, and
hands each presenter that is a `CommandPresenter` the binder
(`ICommandBinder`, the Engine's `ActionRegistry`) as it is built; the
presenter binds a handler, and the state that enables it, for each command
it performs. A command nothing binds stays disabled, and the Engine logs it
once at the end of boot.

A base class rather than a `Protocol`: every implementer is already a
`BasePresenter`, so this is its one base, no second one
(`architecture-rule.md` §2.1, ABC is the default).

@par `@abstractmethod` without `ABC`, the `BaseFeed` pattern
`BasePresenter` is a `QObject`, whose metaclass is Shiboken's, and mixing
`ABCMeta` into it raises a metaclass conflict. So the decorator documents the
contract and the body raises, as `options_section_presenter.py` does.

Plausible extensions, each a local change: a presenter that binds a command
only in developer mode (a branch in its own `bind_commands`); a command bound
from a signal that carries its checked state (already a `bind` argument).
"""

from __future__ import annotations

from abc import abstractmethod

from sagittarius_engine.extensions.pyside_mvc import BasePresenter

from .command_binding import ICommandBinder


class CommandPresenter(BasePresenter):
    """A `BasePresenter` that binds the commands its module contributed."""

    @abstractmethod
    def bind_commands(self, binder: ICommandBinder) -> None:
        """Binds each command this presenter performs."""
        raise NotImplementedError("bind_commands")
