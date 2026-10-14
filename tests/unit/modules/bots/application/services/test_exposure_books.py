"""`EPIC-039D` - a bot asks one question, `held()`, and a Spot and a Futures
answer differ only in kind."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_housekeeping import (
    refusal_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.positions.exposure_books import (
    exposure_book_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_book import (
    Exposure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    VenueProfile,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    ForeignPosition,
    OwnerPosition,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _profile(venue: TradingVenue) -> VenueProfile:
    profile = venue_profile_of(venue)
    assert profile is not None
    return profile


_SPOT = _profile(TradingVenue.SPOT_TESTNET)
_FUTURES = _profile(TradingVenue.FUTURES_TESTNET)


def _spot(quantity: str, cost: str) -> OwnerBudgetRegistrationResult:
    return OwnerBudgetRegistrationResult(
        None, OwnerInventory(Decimal(quantity), Decimal(cost))
    )


def _futures(quantity: str, entry: str | None) -> OwnerBudgetRegistrationResult:
    position = OwnerPosition(
        Decimal(quantity),
        None if entry is None else Decimal(entry),
        Decimal(0),
        Decimal(0),
    )
    return OwnerBudgetRegistrationResult(None, position=position)


def test_a_spot_inventory_is_held_at_its_average_cost() -> None:
    held = exposure_book_of(_SPOT, _spot("0.004", "240")).held()

    assert held == Exposure(ExposureKind.INVENTORY, Decimal("0.004"), Decimal(60000))


def test_a_futures_position_is_held_signed_at_its_average_entry() -> None:
    held = exposure_book_of(_FUTURES, _futures("-0.020", "61000")).held()

    assert held == Exposure(ExposureKind.POSITION, Decimal("-0.020"), Decimal(61000))


@pytest.mark.parametrize(
    ("profile", "registration"),
    [(_SPOT, _spot("0", "0")), (_FUTURES, _futures("0", None))],
)
def test_nothing_held_is_flat_on_either_venue(
    profile: VenueProfile, registration: OwnerBudgetRegistrationResult
) -> None:
    held = exposure_book_of(profile, registration).held()

    assert held.is_flat and held.average_entry is None


def test_an_answer_for_the_other_kind_of_venue_is_refused() -> None:
    with pytest.raises(ValueError, match="no position"):
        exposure_book_of(_FUTURES, _spot("0.1", "10"))
    with pytest.raises(ValueError, match="no inventory"):
        exposure_book_of(_SPOT, _futures("1", "10"))


def test_a_negative_inventory_cannot_be_held() -> None:
    with pytest.raises(ValueError, match="never negative"):
        Exposure(ExposureKind.INVENTORY, Decimal(-1), Decimal(1))


def test_the_foreign_position_refusal_reads_in_the_users_words() -> None:
    refused = OwnerBudgetRegistrationResult(
        OwnerBudgetRefusal.FOREIGN_POSITION,
        foreign_position=ForeignPosition("ETHUSDT", Decimal("0.050")),
    )

    assert refusal_text(refused) == (
        "ETHUSDT already has a long position of 0.05 that this bot did not open; "
        "close it or pick another symbol"
    )
