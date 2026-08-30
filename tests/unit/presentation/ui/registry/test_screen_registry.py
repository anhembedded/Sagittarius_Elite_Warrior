"""`EPIC-016` — `ScreenRegistry` behaviour, independent of any real screen."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.registry import (
    AbstractScreenModule,
    NavLocation,
    ScreenDescriptor,
    ScreenRegistry,
    SectionDescriptor,
)


class _FakeModule(AbstractScreenModule):
    """A minimal, non-Qt stand-in — no real View/Presenter construction, so
    these tests exercise only `ScreenRegistry`'s own bookkeeping."""

    def __init__(
        self,
        route: str,
        *,
        title: str = "",
        icon: str = "",
        section_key: str = "NAVIGATION",
        section_sequence: int = 100,
        item_sequence: int = 100,
        is_default: bool = False,
        location: NavLocation = NavLocation.TOP_SECTION,
    ) -> None:
        self._route = route
        self._title = title or route
        self._icon = icon
        self._section_key = section_key
        self._section_sequence = section_sequence
        self._item_sequence = item_sequence
        self._is_default = is_default
        self._location = location

    @property
    def route(self) -> str:
        return self._route

    @property
    def title(self) -> str:
        return self._title

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def section_key(self) -> str:
        return self._section_key

    @property
    def section_sequence(self) -> int:
        return self._section_sequence

    @property
    def item_sequence(self) -> int:
        return self._item_sequence

    @property
    def is_default(self) -> bool:
        return self._is_default

    @property
    def location(self) -> NavLocation:
        return self._location

    def create_view(self, container):
        return Mock()

    def create_presenter(self, view, container):
        return Mock()


@pytest.fixture
def registry() -> ScreenRegistry:
    return ScreenRegistry()


@pytest.fixture
def container() -> Mock:
    return Mock()


def test_register_module_then_get_returns_its_descriptor(registry, container) -> None:
    registry.register_module(_FakeModule("dashboard", title="Dev Board"), container)
    descriptor = registry.get("dashboard")
    assert descriptor.route == "dashboard"
    assert descriptor.nav is not None
    assert descriptor.nav.title == "Dev Board"


def test_get_unknown_route_raises_key_error(registry) -> None:
    with pytest.raises(KeyError):
        registry.get("nope")


def test_get_default_route_raises_when_nothing_declared_default(registry) -> None:
    with pytest.raises(RuntimeError):
        registry.get_default_route()


def test_duplicate_route_raises_value_error(registry, container) -> None:
    registry.register_module(_FakeModule("dashboard"), container)
    with pytest.raises(ValueError, match="dashboard"):
        registry.register_module(_FakeModule("dashboard"), container)


def test_two_default_screens_raises_value_error(registry, container) -> None:
    registry.register_module(_FakeModule("a", is_default=True), container)
    with pytest.raises(ValueError, match="is_default"):
        registry.register_module(_FakeModule("b", is_default=True), container)


def test_build_sidebar_navigation_sorts_sections_then_items(
    registry, container
) -> None:
    registry.register_module(
        _FakeModule(
            "backtest", title="Backtest", section_key="QUANT", section_sequence=20
        ),
        container,
    )
    registry.register_module(
        _FakeModule(
            "dashboard",
            title="Dev Board",
            section_key="NAV",
            section_sequence=10,
            item_sequence=10,
        ),
        container,
    )
    registry.register_module(
        _FakeModule(
            "data_management",
            title="Database",
            section_key="NAV",
            section_sequence=10,
            item_sequence=20,
        ),
        container,
    )

    sections, bottom = registry.build_sidebar_navigation()

    assert [s.title for s in sections] == ["NAV", "QUANT"]
    assert [item.label for item in sections[0].items] == ["Dev Board", "Database"]
    assert [item.label for item in sections[1].items] == ["Backtest"]
    assert bottom == ()


def test_build_sidebar_navigation_puts_bottom_action_screens_aside(
    registry, container
) -> None:
    registry.register_module(_FakeModule("dashboard"), container)
    registry.register_module(
        _FakeModule("settings", title="Settings", location=NavLocation.BOTTOM_ACTION),
        container,
    )

    sections, bottom = registry.build_sidebar_navigation()

    assert len(sections) == 1
    assert [item.label for item in bottom] == ["Settings"]


def test_item_sequence_tie_break_is_deterministic_by_route(registry, container) -> None:
    registry.register_module(
        _FakeModule("b_route", title="B", section_key="NAV", item_sequence=10),
        container,
    )
    registry.register_module(
        _FakeModule("a_route", title="A", section_key="NAV", item_sequence=10),
        container,
    )

    sections, _bottom = registry.build_sidebar_navigation()

    assert [item.route for item in sections[0].items] == ["a_route", "b_route"]


def test_conflicting_section_sequence_across_modules_raises(
    registry, container
) -> None:
    registry.register_module(
        _FakeModule("a", section_key="NAV", section_sequence=10), container
    )
    with pytest.raises(ValueError, match="Xung đột section_sequence"):
        registry.register_module(
            _FakeModule("b", section_key="NAV", section_sequence=999), container
        )


def test_register_section_locks_the_sequence_explicitly(registry, container) -> None:
    registry.register_section(
        SectionDescriptor(key="NAV", title="Navigation", sequence=5)
    )
    registry.register_module(
        _FakeModule("a", section_key="NAV", section_sequence=5), container
    )

    sections, _bottom = registry.build_sidebar_navigation()

    assert sections[0].title == "Navigation"


def test_bind_to_router_registers_every_screen(registry, container) -> None:
    registry.register_module(_FakeModule("dashboard"), container)
    registry.register_module(_FakeModule("backtest"), container)
    router = Mock()

    registry.bind_to_router(router)

    assert router.register.call_count == 2
    registered_routes = {call.args[0] for call in router.register.call_args_list}
    assert registered_routes == {"dashboard", "backtest"}


def test_register_accepts_a_raw_descriptor_without_a_module(registry) -> None:
    """`register()` is available without `AbstractScreenModule` ceremony —
    e.g. for a test double that wants a screen without a real module."""
    descriptor = ScreenDescriptor(
        route="fake",
        presenter_class=lambda v, c: Mock(),
        view_factory=lambda: Mock(),
    )
    registry.register(descriptor)
    assert registry.get("fake") is descriptor
