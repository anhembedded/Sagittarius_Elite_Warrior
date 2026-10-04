"""`EPIC-016` — the concrete `IScreenRegistry` adapter."""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import (
    NavLocation,
    NavMetadata,
)

from .models.screen_descriptor import ScreenDescriptor
from .models.section_descriptor import SectionDescriptor
from .ports.i_screen_registry import IScreenRegistry

_DEFAULT_ITEM_SEQUENCE = 100


class ScreenRegistry(IScreenRegistry):
    def __init__(self) -> None:
        self._descriptors: dict[str, ScreenDescriptor] = {}
        self._sections: dict[str, SectionDescriptor] = {}
        self._default_route: str | None = None

    def register(self, descriptor: ScreenDescriptor) -> None:
        """`EPIC-025`: registers a screen descriptor and reconciles its
        section sequence."""
        if descriptor.route in self._descriptors:
            raise ValueError(
                f"Route '{descriptor.route}' already exists in ScreenRegistry!"
            )
        if descriptor.is_default:
            if self._default_route is not None:
                raise ValueError(
                    f"Default screen conflict: '{descriptor.route}' and "
                    f"'{self._default_route}' both declare is_default=True."
                )
            self._default_route = descriptor.route
        self._descriptors[descriptor.route] = descriptor
        nav = descriptor.nav
        if nav is not None and nav.location == NavLocation.TOP_SECTION:
            self._reconcile_section(nav.section_key, nav.section_sequence)

    def register_section(self, section: SectionDescriptor) -> None:
        """Explicit call — the single source of truth for this section's
        `sequence` from now on, whether called before or after the screens
        that belong to it."""
        self._sections[section.key] = section

    def _reconcile_section(self, key: str, sequence: int) -> None:
        existing = self._sections.get(key)
        if existing is None:
            self._sections[key] = SectionDescriptor(
                key=key, title=key.upper(), sequence=sequence
            )
            return
        if existing.sequence != sequence:
            raise ValueError(
                f"section_sequence conflict for section '{key}': already registered "
                f"as {existing.sequence}, new module declares {sequence}. Call "
                "register_section() to pin an explicit value."
            )

    def get(self, route: str) -> ScreenDescriptor:
        try:
            return self._descriptors[route]
        except KeyError:
            raise KeyError(route) from None

    def get_all(self) -> Sequence[ScreenDescriptor]:
        return tuple(self._descriptors.values())

    def get_default_route(self) -> str:
        if self._default_route is None:
            raise RuntimeError("no screen declared is_default=True")
        return self._default_route

    def modes(self) -> Sequence[ScreenDescriptor]:
        navigable = [
            (descriptor, descriptor.nav)
            for descriptor in self._descriptors.values()
            if descriptor.nav is not None and descriptor.nav.is_navigable
        ]
        # `route` as the last key keeps the order deterministic when two
        # screens share a sequence — never left to insertion order.
        return tuple(
            descriptor
            for descriptor, nav in sorted(
                navigable,
                key=lambda pair: (
                    pair[1].location == NavLocation.BOTTOM_ACTION,
                    self._section_sequence(pair[1]),
                    pair[1].item_sequence,
                    pair[0].route,
                ),
            )
        )

    def _section_sequence(self, nav: NavMetadata) -> int:
        if nav.location == NavLocation.BOTTOM_ACTION:
            return 0
        section = self._sections.get(nav.section_key)
        return section.sequence if section is not None else _DEFAULT_ITEM_SEQUENCE
