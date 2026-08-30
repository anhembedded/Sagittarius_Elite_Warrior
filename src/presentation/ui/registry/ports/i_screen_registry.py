"""`EPIC-016` — the port `MainWindow` depends on instead of every concrete
screen. `abc.ABC`: none of `architecture-rule.md` §2.1's Protocol exceptions
apply to the adapter that will implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import (
    NavItem,
    NavSection,
)
from sagittarius_engine.extensions.pyside_mvc import PresenterManager
from sagittarius_engine.interfaces.i_container import IContainer

from ..abstract_screen_module import AbstractScreenModule
from ..models.screen_descriptor import ScreenDescriptor
from ..models.section_descriptor import SectionDescriptor


class IScreenRegistry(ABC):
    """Catalogue of every screen and the sidebar structure they build."""

    @abstractmethod
    def register(self, descriptor: ScreenDescriptor) -> None:
        """Registers a fully-built descriptor directly — the path
        `register_module()` uses internally, and available to a caller that
        does not want the `AbstractScreenModule` ceremony (e.g. a test
        double). Raises `ValueError` on a duplicate `route`, or a second
        `is_default=True` screen."""
        ...

    @abstractmethod
    def register_module(
        self, module: AbstractScreenModule, container: IContainer
    ) -> None:
        """Builds `module`'s descriptor against `container` and registers it."""
        ...

    @abstractmethod
    def register_section(self, section: SectionDescriptor) -> None:
        """Declares a section's title/sequence explicitly — the single
        source of truth for that section's `sequence` once called; see
        `register_module()`'s own contract for what happens without it."""
        ...

    @abstractmethod
    def get(self, route: str) -> ScreenDescriptor:
        """Raises `KeyError(route)` if nothing registered that route."""
        ...

    @abstractmethod
    def get_all(self) -> Sequence[ScreenDescriptor]: ...

    @abstractmethod
    def get_default_route(self) -> str:
        """Raises `RuntimeError` if no registered module declared
        `is_default=True`."""
        ...

    @abstractmethod
    def build_sidebar_navigation(
        self,
    ) -> tuple[Sequence[NavSection], Sequence[NavItem]]:
        """Sections and bottom actions, sorted by section then item
        sequence, ready for `Sidebar`'s constructor."""
        ...

    @abstractmethod
    def bind_to_router(self, router: PresenterManager) -> None:
        """Registers every screen's route with `router` (lazy — this only
        calls `router.register()`, it never constructs a View or Presenter)."""
        ...
