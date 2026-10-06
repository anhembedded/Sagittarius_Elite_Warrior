"""`EPIC-021K` §4 — "banner hiện đúng ở cả 5 màn — quét registry, không liệt
kê tay từng màn".

@details Scans `real_screen_registry()` (`EPIC-016`) the same way
`tests/sanity/test_composition_root.py::test_every_navigable_route_constructs`
does, rather than hand-listing the 5 screens here — a 6th screen added later
is covered automatically, and this file never has to be told about it.

Only `create_view()` is exercised (a `Mock()` container is enough — see
`_navigable_routes()`'s own docstring in `test_composition_root.py`): the
banner is `WorkbenchSurface.set_environment_banner_factory`'s job, which every
View picks up purely by constructing its `WorkbenchSurface`, with no Presenter
involved (`EPIC-033M` deleted the other shell, `PageShell`).
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    EnvironmentBanner,
    venue_alignment_banner_content,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)


def _navigable_routes():
    from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry

    registry = real_screen_registry(Mock())
    return [d.route for d in registry.get_all() if d.has_nav()]


@pytest.fixture
def _environment_banner_factory_registered():
    """Mirrors what `app_bootstrapper.build()` does at boot — registered
    here directly (not via a full app boot) because `create_view()` needs
    nothing else `booted_app` would provide.
    """
    content = venue_alignment_banner_content(VenueAlignment.ALIGNED)
    WorkbenchSurface.set_environment_banner_factory(lambda: EnvironmentBanner(content))
    yield
    WorkbenchSurface.set_environment_banner_factory(None)


@pytest.mark.parametrize("route", _navigable_routes())
def test_every_screen_shows_the_environment_banner(
    qapp, route, _environment_banner_factory_registered
) -> None:
    from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry

    registry = real_screen_registry(Mock())
    descriptor = registry.get(route)
    view = descriptor.view_factory()
    try:
        banner = view.findChild(QWidget, "environmentBanner")
        assert banner is not None, (
            f"Route '{route}' built a View with no environmentBanner widget "
            f"in its tree. Every screen sits on a shell that fills the slot "
            f"itself, `WorkbenchSurface`, so this means that screen's View "
            f"builds none, or builds a layout of its own."
        )
    finally:
        view.deleteLater()
        qapp.processEvents()
