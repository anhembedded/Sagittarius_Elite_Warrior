"""`EPIC-039D` — the bot's `IExposureBook`, over what trading derived.

@details Trading derives the holding (an `OwnerInventory` on Spot, an
`OwnerPosition` on Futures) and returns it in the answer to the bot's budget
registration; these adapters give both the one question `held()` (`IExposureBook`).
`exposure_book_of` chooses by the venue profile's exposure kind, the one place
that choice is made.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_book import (
    Exposure,
    IExposureBook,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    VenueProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
)


class SpotExposureBook(IExposureBook):
    """The base the bot bought and still holds, at its average cost."""

    def __init__(self, inventory: OwnerInventory) -> None:
        self._inventory = inventory

    def held(self) -> Exposure:
        inventory = self._inventory
        if inventory.quantity <= 0:
            return Exposure(ExposureKind.INVENTORY, Decimal(0), None)
        return Exposure(
            ExposureKind.INVENTORY,
            inventory.quantity,
            inventory.cost / inventory.quantity,
        )


class FuturesExposureBook(IExposureBook):
    """The signed position the bot holds, at its average entry."""

    def __init__(self, position: OwnerPosition) -> None:
        self._position = position

    def held(self) -> Exposure:
        position = self._position
        return Exposure(
            ExposureKind.POSITION, position.quantity, position.average_entry
        )


def exposure_book_of(
    profile: VenueProfile, registration: OwnerBudgetRegistrationResult
) -> IExposureBook:
    """@brief The book for a registered bot on `profile`'s venue.
    @throws ValueError `registration` carries no holding of the profile's kind
    (it was refused, or answered for the other kind of venue)."""
    if profile.exposure_kind is ExposureKind.POSITION:
        if registration.position is None:
            raise ValueError("the registration carries no position")
        return FuturesExposureBook(registration.position)
    if registration.inventory is None:
        raise ValueError("the registration carries no inventory")
    return SpotExposureBook(registration.inventory)
