"""`EPIC-035P` — the run's memory of which fills it has counted stays bounded."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.applied_fills import (
    AppliedFills,
)


def test_a_fill_is_known_once_it_is_recorded() -> None:
    fills = AppliedFills()
    assert not fills.knows("SEW-a-1", 11)

    fills.record("SEW-a-1", 11)

    assert fills.knows("SEW-a-1", 11)
    assert not fills.knows("SEW-a-1", 12)
    assert not fills.knows("SEW-a-2", 11)


def test_a_fill_without_a_trade_id_is_never_known() -> None:
    fills = AppliedFills()

    fills.record("SEW-a-1", None)

    assert not fills.knows("SEW-a-1", None)


def test_the_oldest_fills_are_forgotten_beyond_the_limit() -> None:
    fills = AppliedFills(limit=3)
    for trade_id in range(1, 5):
        fills.record("SEW-a-1", trade_id)

    assert not fills.knows("SEW-a-1", 1)
    assert all(fills.knows("SEW-a-1", trade_id) for trade_id in (2, 3, 4))


def test_recording_a_known_fill_again_does_not_age_out_a_newer_one() -> None:
    fills = AppliedFills(limit=2)
    fills.record("SEW-a-1", 1)
    fills.record("SEW-a-1", 2)

    fills.record("SEW-a-1", 2)

    assert fills.knows("SEW-a-1", 1) and fills.knows("SEW-a-1", 2)
