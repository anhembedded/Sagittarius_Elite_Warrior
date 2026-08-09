from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    """
    @brief One clickable (or deliberately disabled) entry in the sidebar.

    @param label Text shown to the user, e.g. "Dev Board".
    @param route The PresenterManager route key this entry navigates to, or
    None for a placeholder whose screen doesn't exist yet.
    @param icon Lucide icon stem, e.g. "layout-dashboard" (see assets/icons/).
    @param enabled False renders the entry dimmed and non-interactive.

    @details A routeless entry is ALWAYS non-navigable regardless of
    `enabled` — see `is_navigable`. That keeps "no screen registered" from
    silently becoming a dead link if someone flips `enabled` to True without
    also registering a route.
    """

    label: str
    route: str | None
    icon: str
    enabled: bool = True

    @property
    def is_navigable(self) -> bool:
        return self.enabled and self.route is not None


@dataclass(frozen=True)
class NavSection:
    """@brief A titled group of nav entries, e.g. "NAVIGATION" / "QUANT ENGINE"."""

    title: str
    items: tuple[NavItem, ...]
