"""`EPIC-016` — one screen's route registration, in the shape
`PresenterManager.register()` actually consumes.

@details `presenter_class`/`view_factory` are `Callable`, not `type` — the
real engine (`sagittarius_engine.extensions.pyside_mvc.mvc.presenter_manager`,
confirmed against the real source in `EPIC-016A`) calls
`view_factory()` with zero arguments and `presenter_class(view, container)`
with two; `AbstractScreenModule.build_descriptor()` supplies both as small
lambdas, not classes, so a `type` annotation would be a lie about what this
field actually holds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sagittarius_engine.extensions.pyside_mvc import BasePresenter, BaseView
from sagittarius_engine.interfaces.i_container import IContainer

from .nav_metadata import NavMetadata


@dataclass(frozen=True, slots=True)
class ScreenDescriptor:
    """Everything `ScreenRegistry` needs to route to, and optionally
    navigate to, one screen."""

    route: str
    presenter_class: Callable[[BaseView, IContainer], BasePresenter]
    view_factory: Callable[[], BaseView]
    nav: NavMetadata | None = None
    is_default: bool = False

    def has_nav(self) -> bool:
        """Whether this screen appears on the sidebar at all."""
        return self.nav is not None
