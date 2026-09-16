from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TabFullPresentation:
    """
    @brief Visual and textual representation of a tab in the expanded sidebar.

    @param label The primary text label (e.g., 'Dev Board', 'Backtest Engine').
    @param route The destination route key or None.
    @param badge Optional badge string (e.g., 'NEW', 'BETA', '9+').
    @param description Optional subtitle or explanatory text.
    """

    label: str
    route: str | None = None
    badge: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class TabIconPresentation:
    """
    @brief Compact representation of a tab in the collapsed activity rail.

    @param icon Lucide icon stem name (e.g., 'layout-dashboard', 'database').
    @param tooltip Hover tooltip text shown to the user in collapsed mode.
    @param badge Optional mini badge count or indicator dot.
    """

    icon: str
    tooltip: str
    badge: str | None = None


@runtime_checkable
class ITab(Protocol):
    """
    @brief Interface Segregation / Open-Closed Principle contract for Sidebar Tabs.

    @details
    Every sidebar tab encapsulates its identity, navigability logic, and two
    distinct visual representations:
    1. `tab_full`: Rich metadata for the expanded (220px) sidebar mode.
    2. `tab_icon`: Streamlined metadata for the compact (48px) VS Code style icon rail.

    New tab types (e.g., ActionTab, DynamicBadgeTab, ExternalLinkTab) can be
    implemented by fulfilling this contract without modifying Sidebar or ViewModel.
    """

    @property
    def id(self) -> str:
        """Unique identifier string for this tab."""
        ...

    @property
    def route(self) -> str | None:
        """The navigation route key, or None for non-navigable / action tabs."""
        ...

    @property
    def is_navigable(self) -> bool:
        """True if activating this tab triggers router navigation."""
        ...

    @property
    def is_enabled(self) -> bool:
        """True if this tab is interactive and not dimmed."""
        ...

    @property
    def tab_full(self) -> TabFullPresentation:
        """Full expanded presentation metadata."""
        ...

    @property
    def tab_icon(self) -> TabIconPresentation:
        """Compact icon-only presentation metadata."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serializes the tab to a dictionary consumed by QML models."""
        ...
