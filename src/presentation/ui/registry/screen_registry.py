"""`EPIC-016` — the concrete `IScreenRegistry` adapter."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import (
    NavItem,
    NavSection,
)
from sagittarius_engine.extensions.pyside_mvc import PresenterManager
from sagittarius_engine.interfaces.i_container import IContainer

from .abstract_screen_module import AbstractScreenModule
from .models.nav_metadata import NavLocation, NavMetadata
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
        if descriptor.route in self._descriptors:
            raise ValueError(
                f"Route '{descriptor.route}' đã tồn tại trong ScreenRegistry!"
            )
        if descriptor.is_default:
            if self._default_route is not None:
                raise ValueError(
                    f"Xung đột màn hình mặc định: '{descriptor.route}' và "
                    f"'{self._default_route}' đều khai báo is_default=True."
                )
            self._default_route = descriptor.route
        self._descriptors[descriptor.route] = descriptor

    def register_module(
        self, module: AbstractScreenModule, container: IContainer
    ) -> None:
        descriptor = module.build_descriptor(container)
        self.register(descriptor)
        nav = descriptor.nav
        if nav is not None and nav.location == NavLocation.TOP_SECTION:
            self._reconcile_section(nav.section_key, nav.section_sequence)

    def register_section(self, section: SectionDescriptor) -> None:
        """Explicit call — the single source of truth for this section's
        `sequence` from now on, whether called before or after the modules
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
                f"Xung đột section_sequence cho section '{key}': đã đăng ký "
                f"{existing.sequence}, module mới khai {sequence}. Gọi "
                "register_section() để chốt một giá trị tường minh."
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
            raise RuntimeError("no ScreenModule declared is_default=True")
        return self._default_route

    def build_sidebar_navigation(
        self,
    ) -> tuple[Sequence[NavSection], Sequence[NavItem]]:
        # `(route, nav)` rather than the whole `ScreenDescriptor`: `nav` is
        # `NavMetadata | None` on the descriptor, but every entry that
        # reaches these two collections has already passed the `nav is None`
        # check below, so the pair type says that once, instead of every
        # reader having to re-derive (or assert) it downstream.
        sections_items: dict[str, list[tuple[str, NavMetadata]]] = defaultdict(list)
        bottom_entries: list[tuple[str, NavMetadata]] = []

        for descriptor in self._descriptors.values():
            nav = descriptor.nav
            if nav is None:
                continue
            if nav.location == NavLocation.BOTTOM_ACTION:
                bottom_entries.append((descriptor.route, nav))
            else:
                sections_items[nav.section_key].append((descriptor.route, nav))

        sorted_section_keys = sorted(
            sections_items.keys(),
            key=lambda key: (
                self._sections[key].sequence
                if key in self._sections
                else _DEFAULT_ITEM_SEQUENCE
            ),
        )

        built_sections: list[NavSection] = []
        for section_key in sorted_section_keys:
            sorted_entries = self._sort_by_item_sequence(sections_items[section_key])
            items = tuple(
                self._to_nav_item(route, nav) for route, nav in sorted_entries
            )
            title = (
                self._sections[section_key].title
                if section_key in self._sections
                else section_key.upper()
            )
            built_sections.append(NavSection(title, items))

        sorted_bottom = self._sort_by_item_sequence(bottom_entries)
        built_bottom = tuple(
            self._to_nav_item(route, nav) for route, nav in sorted_bottom
        )

        return tuple(built_sections), built_bottom

    @staticmethod
    def _sort_by_item_sequence(
        entries: list[tuple[str, NavMetadata]],
    ) -> list[tuple[str, NavMetadata]]:
        # `route` as the tie-break keeps the ordering deterministic when two
        # screens share an `item_sequence` — never left to dict/list
        # insertion order, which is an implementation detail, not a contract.
        return sorted(entries, key=lambda entry: (entry[1].item_sequence, entry[0]))

    @staticmethod
    def _to_nav_item(route: str, nav: NavMetadata) -> NavItem:
        return NavItem(
            label=nav.title, route=route, icon=nav.icon, enabled=nav.is_navigable
        )

    def bind_to_router(self, router: PresenterManager) -> None:
        for descriptor in self._descriptors.values():
            router.register(
                descriptor.route, descriptor.presenter_class, descriptor.view_factory
            )
