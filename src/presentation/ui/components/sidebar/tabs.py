from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .tab_interface import ITab, TabFullPresentation, TabIconPresentation


@dataclass(frozen=True)
class SidebarTab(ITab):
    """
    @brief Base concrete implementation of ITab for sidebar navigation.

    @param label The text displayed to the user in expanded view.
    @param route The PresenterManager route key, or None if non-navigable.
    @param icon Lucide vector icon stem name (e.g., 'layout-dashboard').
    @param enabled Whether the tab is interactive (default: True).
    @param badge Optional badge text displayed on the tab (e.g., 'NEW').
    @param description Optional subtitle for the expanded view.
    @param tooltip Optional custom tooltip for the collapsed view (defaults to label).
    """

    label: str
    route: str | None = None
    icon: str = ""
    enabled: bool = True
    badge: str | None = None
    description: str | None = None
    tooltip: str | None = None

    @property
    def id(self) -> str:
        return self.route or self.label.lower().replace(" ", "_")

    @property
    def is_navigable(self) -> bool:
        """A routeless entry is ALWAYS non-navigable regardless of `enabled`."""
        return self.enabled and self.route is not None

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    @property
    def tab_full(self) -> TabFullPresentation:
        return TabFullPresentation(
            label=self.label,
            route=self.route,
            badge=self.badge,
            description=self.description,
        )

    @property
    def tab_icon(self) -> TabIconPresentation:
        tip = self.tooltip
        if tip is None:
            tip = self.label if self.is_navigable else f"{self.label} (Sắp ra mắt)"
        return TabIconPresentation(
            icon=self.icon,
            tooltip=tip,
            badge=self.badge,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.tab_full.label,
            "route": self.route or "",
            "icon": self.tab_icon.icon,
            "tooltip": self.tab_icon.tooltip,
            "badge": self.badge or "",
            "description": self.description or "",
            "navigable": self.is_navigable,
            "enabled": self.is_enabled,
        }


@dataclass(frozen=True)
class RouteTab(SidebarTab):
    """
    @brief Dedicated tab class representing standard screen route navigation.
    """


@dataclass(frozen=True)
class ActionTab(SidebarTab):
    """
    @brief Action tab that triggers a custom Python callable or event rather than route change.
    """

    on_action: Callable[[], None] | None = None

    @property
    def is_navigable(self) -> bool:
        return False


@dataclass(frozen=True)
class DisabledTab(SidebarTab):
    """
    @brief Explicit placeholder tab for upcoming features / unreleased screens.
    """

    enabled: bool = False


@dataclass(frozen=True)
class SidebarSection:
    """
    @brief Group of sidebar tabs under a shared section header (e.g. 'NAVIGATION').
    """

    title: str
    items: tuple[ITab, ...]

    def __init__(self, title: str, items: Sequence[ITab]) -> None:
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "items", tuple(items))

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "items": [item.to_dict() for item in self.items],
        }


# Backward-compatible aliases for existing codebase callers
NavItem = SidebarTab
NavSection = SidebarSection
