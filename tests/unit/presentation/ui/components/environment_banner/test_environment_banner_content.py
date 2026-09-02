from __future__ import annotations

from Sagittarius_Elite_Warrior.src.domain.value_objects.venue_alignment import (
    VenueAlignment,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.environment_banner import (
    venue_alignment_banner_content,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.surfaces.banner import Severity


def test_every_alignment_state_has_content() -> None:
    for alignment in VenueAlignment:
        content = venue_alignment_banner_content(alignment)
        assert content.message
        assert content.icon
        assert content.severity in (
            Severity.INFO,
            Severity.WARN,
            Severity.DANGER,
            Severity.SUCCESS,
        )


def test_trading_disabled_says_view_only() -> None:
    content = venue_alignment_banner_content(VenueAlignment.TRADING_DISABLED)
    assert "TẮT" in content.message


def test_mainnet_data_trap_names_both_venues() -> None:
    content = venue_alignment_banner_content(VenueAlignment.DATA_MAINNET_ORDERS_TESTNET)
    assert "MAINNET" in content.message
    assert "TESTNET" in content.message
    assert content.severity is Severity.DANGER


def test_each_alignment_state_maps_to_a_distinct_severity() -> None:
    severities = {
        alignment: venue_alignment_banner_content(alignment).severity
        for alignment in VenueAlignment
    }
    assert len(set(severities.values())) == len(VenueAlignment)
