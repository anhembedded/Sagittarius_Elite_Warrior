"""`EPIC-016` — the base every screen module implements.

@details `abc.ABC`, not `Protocol` — `architecture-rule.md` §2.1's default.
None of the three Protocol exceptions apply: a screen module is a small,
otherwise-unused Elite class (not a `QObject`), free to have any base at
all, so nothing forces a structural contract here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer

from .models.nav_metadata import NavLocation, NavMetadata
from .models.screen_descriptor import ScreenDescriptor


class AbstractScreenModule(ABC):
    """One screen's route, nav placement, and how to build its View/Presenter.

    @details Subclasses implement `create_view()`/`create_presenter()` with
    lazy imports of their concrete View/Presenter classes inside the method
    body, not at module top-level — the same discipline `backtest`'s and
    `data_management`'s heavy screens already follow, so registering every
    module at boot does not pull in every screen's dependency tree before
    the user has navigated to any of them (`PresenterManager` is a *true*
    lazy router; see its own docstring).
    """

    @property
    @abstractmethod
    def route(self) -> str:
        """This screen's unique `PresenterManager` route key."""
        ...

    @property
    @abstractmethod
    def title(self) -> str:
        """Label shown on the sidebar."""
        ...

    @property
    @abstractmethod
    def icon(self) -> str:
        """Lucide icon stem name, as `Sidebar`'s `ITab.icon` expects."""
        ...

    @property
    def section_key(self) -> str:
        return "NAVIGATION"

    @property
    def section_sequence(self) -> int:
        return 100

    @property
    def item_sequence(self) -> int:
        return 100

    @property
    def location(self) -> NavLocation:
        return NavLocation.TOP_SECTION

    @property
    def is_default(self) -> bool:
        """Whether this is the screen `MainWindow` opens on boot."""
        return False

    @property
    def is_navigable(self) -> bool:
        return True

    @abstractmethod
    def create_view(self, container: IContainer) -> BaseView: ...

    @abstractmethod
    def create_presenter(
        self, view: BaseView, container: IContainer
    ) -> BasePresenter: ...

    def build_descriptor(self, container: IContainer) -> ScreenDescriptor:
        """Packages this module into the `ScreenDescriptor` the registry
        stores. `container` is captured by `view_factory`'s closure (not
        passed to `create_view` again at call time) because
        `PresenterManager.view_factory()` is invoked with zero arguments —
        the container this screen builds against is fixed the moment it is
        registered, which matches every other screen: the app has exactly
        one container for its whole lifetime."""
        nav = NavMetadata(
            title=self.title,
            icon=self.icon,
            section_key=self.section_key,
            section_sequence=self.section_sequence,
            item_sequence=self.item_sequence,
            location=self.location,
            is_navigable=self.is_navigable,
        )
        return ScreenDescriptor(
            route=self.route,
            presenter_class=lambda view, c: self.create_presenter(view, c),
            view_factory=lambda: self.create_view(container),
            nav=nav,
            is_default=self.is_default,
        )
