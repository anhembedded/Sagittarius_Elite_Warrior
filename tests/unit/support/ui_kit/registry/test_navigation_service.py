"""`EPIC-025F` — `NavigationService`, independent of any real screen or
router. `PresenterManager` is mocked with `spec=` (an Engine class, not a
module port — `architecture-rule.md` §3's Shared Kernel/module-port
distinction; `tests/unit/architecture/test_no_foreign_port_is_mocked.py`
only fires on a module's own contracts)."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import NavigationService
from sagittarius_engine.extensions.pyside_mvc import PresenterManager


def _service(*, can_leave=None) -> tuple[NavigationService, Mock]:
    router = Mock(spec=PresenterManager)
    return NavigationService(router, can_leave=can_leave), router


def test_navigate_delegates_to_the_router_and_returns_true() -> None:
    service, router = _service()

    moved = service.navigate("dashboard", source=NavigationSource.USER_INTENT)

    assert moved is True
    router.navigate_to.assert_called_once_with("dashboard")


def test_current_source_starts_as_none_before_any_navigation() -> None:
    service, _router = _service()

    assert service.current_source is None


def test_current_source_tracks_the_most_recent_successful_navigation() -> None:
    service, _router = _service()

    service.navigate("dashboard", source=NavigationSource.RESTORE)
    assert service.current_source is NavigationSource.RESTORE

    service.navigate("trading", source=NavigationSource.USER_INTENT)
    assert service.current_source is NavigationSource.USER_INTENT


def test_can_leave_false_refuses_the_navigation() -> None:
    service, router = _service(can_leave=lambda: False)

    moved = service.navigate("trading", source=NavigationSource.USER_INTENT)

    assert moved is False
    router.navigate_to.assert_not_called()
    assert service.current_source is None


def test_can_leave_true_allows_the_navigation() -> None:
    service, router = _service(can_leave=lambda: True)

    moved = service.navigate("trading", source=NavigationSource.USER_INTENT)

    assert moved is True
    router.navigate_to.assert_called_once_with("trading")
    assert service.current_source is NavigationSource.USER_INTENT


def test_can_leave_is_actually_consulted_not_decorative() -> None:
    """Mutation check (`pr-review` E12): a guard nobody reads would pass
    every test above just as happily. Prove the constructor argument is
    truly wired by calling it and observing the effect a removed check
    would erase."""
    calls: list[str] = []

    def can_leave() -> bool:
        calls.append("checked")
        return False

    service, router = _service(can_leave=can_leave)

    service.navigate("trading", source=NavigationSource.USER_INTENT)

    assert calls == ["checked"]
    router.navigate_to.assert_not_called()
