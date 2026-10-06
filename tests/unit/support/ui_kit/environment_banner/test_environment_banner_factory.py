"""`BUG-156`: "Trading is OFF. Data view only." took a full-width strip under the
toolbar of every mode, all day, to say what the window title and the status
bar's venue label already say. A strip is for what must interrupt: the venue
situations that can lose money. The calm one is left to those two places."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.venue_alignment import (
    VenueAlignment,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    EnvironmentBanner,
    environment_banner_factory,
    venue_alignment_banner_content,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)


def _surface_under(alignment: VenueAlignment) -> WorkbenchSurface:
    content = venue_alignment_banner_content(alignment)
    WorkbenchSurface.set_environment_banner_factory(environment_banner_factory(content))
    try:
        surface = WorkbenchSurface(surfaces_by_id()["trading"])
    finally:
        WorkbenchSurface.set_environment_banner_factory(None)
    return surface


def test_trading_off_takes_no_strip(qapp) -> None:
    surface = _surface_under(VenueAlignment.TRADING_DISABLED)
    assert surface.menuWidget() is None
    assert Place.WORKSPACE in surface.accepts()


@pytest.mark.parametrize(
    "alignment",
    [a for a in VenueAlignment if a is not VenueAlignment.TRADING_DISABLED],
)
def test_every_other_venue_situation_keeps_its_strip(
    qapp, alignment: VenueAlignment
) -> None:
    surface = _surface_under(alignment)
    banner = surface.menuWidget()
    assert isinstance(banner, EnvironmentBanner)
    assert banner.message
