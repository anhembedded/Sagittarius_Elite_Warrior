"""`EPIC-016` — the port `MainWindow` depends on instead of every concrete
screen. `abc.ABC`: none of `architecture-rule.md` §2.1's Protocol exceptions
apply to the adapter that will implement this.

Since `EPIC-033D` it also carries the commands the modules contributed with
their screens. A desk's presenter binds its desk's commands as the window
builds it, so a window given the screens without their commands could not
build. Both arrive in this one object, from one `build_screen_registry`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

from ..models.screen_descriptor import ScreenDescriptor
from ..models.section_descriptor import SectionDescriptor


class IScreenRegistry(ABC):
    """Catalogue of every screen, the order the mode bar shows them in, and
    the commands contributed with them."""

    @abstractmethod
    def register(self, descriptor: ScreenDescriptor) -> None:
        """Registers a fully-built descriptor directly. Raises `ValueError`
        on a duplicate `route`, or a second `is_default=True` screen."""
        ...

    @abstractmethod
    def register_section(self, section: SectionDescriptor) -> None:
        """Declares a section's title/sequence explicitly — the single
        source of truth for that section's `sequence` once called."""
        ...

    @abstractmethod
    def get(self, route: str) -> ScreenDescriptor:
        """Raises `KeyError(route)` if nothing registered that route."""
        ...

    @abstractmethod
    def get_all(self) -> Sequence[ScreenDescriptor]: ...

    @abstractmethod
    def get_default_route(self) -> str:
        """Raises `RuntimeError` if no registered screen declared
        `is_default=True`."""
        ...

    @abstractmethod
    def modes(self) -> Sequence[ScreenDescriptor]:
        """The navigable screens in mode-bar order (`EPIC-033C`): top
        sections by section then item sequence, bottom actions last; a
        screen with no `nav` or `is_navigable=False` is not a mode."""
        ...

    @abstractmethod
    def register_command(self, command: CommandContribution) -> None:
        """Raises `ValueError` on a duplicate `command_id`."""
        ...

    @abstractmethod
    def commands(self) -> Sequence[CommandContribution]:
        """Every registered command, in registration order."""
        ...
