"""`BUG-156`: a calm banner ("Trading is OFF. Data view only." then) took a
full-width strip under the toolbar of every mode, all day. A strip is for what
must interrupt: which funds a venue trades, simulated or real. A calm content
(`BannerSeverity.INFO`) takes none; `EPIC-034C` removed the one state that was
calm, and the rule stays pinned with a content of its own."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    BannerSeverity as Severity,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.environment_banner import (
    EnvironmentBanner,
    EnvironmentBannerContent,
    environment_banner_factory,
    venue_banner_content,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)


def _surface_under(content: EnvironmentBannerContent) -> WorkbenchSurface:
    WorkbenchSurface.set_environment_banner_factory(environment_banner_factory(content))
    try:
        surface = WorkbenchSurface(surfaces_by_id()["trading"])
    finally:
        WorkbenchSurface.set_environment_banner_factory(None)
    return surface


def test_a_calm_content_takes_no_strip(qapp) -> None:
    calm = EnvironmentBannerContent(icon="i", message="calm", severity=Severity.INFO)
    WorkbenchSurface.set_environment_banner_factory(environment_banner_factory(calm))
    try:
        surface = WorkbenchSurface(surfaces_by_id()["trading"])
    finally:
        WorkbenchSurface.set_environment_banner_factory(None)

    assert surface.menuWidget() is None
    assert Place.WORKSPACE in surface.accepts()


@pytest.mark.parametrize("venue", list(TradingVenue)[1:])
def test_every_venue_keeps_its_strip(qapp, venue: TradingVenue) -> None:
    surface = _surface_under(venue_banner_content((venue,)))
    banner = surface.menuWidget()
    assert isinstance(banner, EnvironmentBanner)
    assert banner.message
