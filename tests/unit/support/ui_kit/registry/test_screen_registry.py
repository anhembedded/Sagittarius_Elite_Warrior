"""`EPIC-016` / `EPIC-025F` — `ScreenRegistry` behaviour, independent of any real screen."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import (
    NavLocation,
    NavMetadata,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    ScreenDescriptor,
    ScreenRegistry,
    SectionDescriptor,
)


def _make_descriptor(
    route: str,
    *,
    title: str = "",
    icon: str = "",
    section_key: str = "NAVIGATION",
    section_sequence: int = 100,
    item_sequence: int = 100,
    is_default: bool = False,
    location: NavLocation = NavLocation.TOP_SECTION,
    navigable: bool = True,
    presenter_class=None,
    view_factory=None,
) -> ScreenDescriptor:
    nav = NavMetadata(
        title=title or route,
        icon=icon,
        section_key=section_key,
        section_sequence=section_sequence,
        item_sequence=item_sequence,
        location=location,
        is_navigable=navigable,
    )
    return ScreenDescriptor(
        route=route,
        presenter_class=presenter_class or (lambda v, c: Mock()),
        view_factory=view_factory or (lambda: Mock()),
        nav=nav,
        is_default=is_default,
    )


@pytest.fixture
def registry() -> ScreenRegistry:
    return ScreenRegistry()


def test_register_then_get_returns_its_descriptor(registry) -> None:
    descriptor = _make_descriptor("dashboard", title="Dev Board")
    registry.register(descriptor)
    retrieved = registry.get("dashboard")
    assert retrieved.route == "dashboard"
    assert retrieved.nav is not None
    assert retrieved.nav.title == "Dev Board"


def test_get_unknown_route_raises_key_error(registry) -> None:
    with pytest.raises(KeyError):
        registry.get("nope")


def test_get_default_route_raises_when_nothing_declared_default(registry) -> None:
    with pytest.raises(RuntimeError):
        registry.get_default_route()


def test_duplicate_route_raises_value_error(registry) -> None:
    registry.register(_make_descriptor("dashboard"))
    with pytest.raises(ValueError, match="dashboard"):
        registry.register(_make_descriptor("dashboard"))


def test_two_default_screens_raises_value_error(registry) -> None:
    registry.register(_make_descriptor("a", is_default=True))
    with pytest.raises(ValueError, match="is_default"):
        registry.register(_make_descriptor("b", is_default=True))


def test_build_sidebar_navigation_sorts_sections_then_items(registry) -> None:
    registry.register(
        _make_descriptor(
            "backtest", title="Backtest", section_key="QUANT", section_sequence=20
        )
    )
    registry.register(
        _make_descriptor(
            "dashboard",
            title="Dev Board",
            section_key="NAV",
            section_sequence=10,
            item_sequence=10,
        )
    )
    registry.register(
        _make_descriptor(
            "data_management",
            title="Database",
            section_key="NAV",
            section_sequence=10,
            item_sequence=20,
        )
    )

    sections, bottom = registry.build_sidebar_navigation()

    assert [s.title for s in sections] == ["NAV", "QUANT"]
    assert [item.label for item in sections[0].items] == ["Dev Board", "Database"]
    assert [item.label for item in sections[1].items] == ["Backtest"]
    assert bottom == ()


def test_build_sidebar_navigation_puts_bottom_action_screens_aside(registry) -> None:
    registry.register(_make_descriptor("dashboard"))
    registry.register(
        _make_descriptor(
            "settings", title="Settings", location=NavLocation.BOTTOM_ACTION
        )
    )

    sections, bottom = registry.build_sidebar_navigation()

    assert len(sections) == 1
    assert [item.label for item in bottom] == ["Settings"]


def test_item_sequence_tie_break_is_deterministic_by_route(registry) -> None:
    registry.register(
        _make_descriptor("b_route", title="B", section_key="NAV", item_sequence=10)
    )
    registry.register(
        _make_descriptor("a_route", title="A", section_key="NAV", item_sequence=10)
    )

    sections, _bottom = registry.build_sidebar_navigation()

    assert [item.route for item in sections[0].items] == ["a_route", "b_route"]


def test_conflicting_section_sequence_across_screens_raises(registry) -> None:
    registry.register(_make_descriptor("a", section_key="NAV", section_sequence=10))
    with pytest.raises(ValueError, match="section_sequence conflict"):
        registry.register(
            _make_descriptor("b", section_key="NAV", section_sequence=999)
        )


def test_register_section_locks_the_sequence_explicitly(registry) -> None:
    registry.register_section(
        SectionDescriptor(key="NAV", title="Navigation", sequence=5)
    )
    registry.register(_make_descriptor("a", section_key="NAV", section_sequence=5))

    sections, _bottom = registry.build_sidebar_navigation()

    assert sections[0].title == "Navigation"


def test_bind_to_router_registers_every_screen(registry) -> None:
    registry.register(_make_descriptor("dashboard"))
    registry.register(_make_descriptor("backtest"))
    router = Mock()

    registry.bind_to_router(router)

    assert router.register.call_count == 2
    registered_routes = {call.args[0] for call in router.register.call_args_list}
    assert registered_routes == {"dashboard", "backtest"}


def test_register_accepts_a_descriptor_without_nav(registry) -> None:
    descriptor = ScreenDescriptor(
        route="fake",
        presenter_class=lambda v, c: Mock(),
        view_factory=lambda: Mock(),
    )
    registry.register(descriptor)
    assert registry.get("fake") is descriptor
