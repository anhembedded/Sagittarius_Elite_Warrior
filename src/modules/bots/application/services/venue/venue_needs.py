"""`EPIC-039H` — what a plan asks of the account, chosen by the venue's exposure kind.

@details `judge_venue` picks the rules by the profile; this picks the needs they judge. A start's
needs on an inventory venue are the quote and base of the ladder (`LadderNeeds`), on a position
venue the margin of its worst case (`FuturesNeeds`). Both come from the plan the executor would
draw, so no screen and no use case keeps a second copy of the sizing.

Extension cases: a third exposure kind is one row in each table.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.futures_ladder_needs import (
    resume_futures_needs,
    start_futures_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.ladder_needs import (
    resume_ladder_needs,
    start_ladder_needs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_rules import (
    VenueNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    VenueProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

type _Start = Callable[[Mapping[str, str], ExchangeTerms, Decimal], VenueNeeds | None]
type _Resume = Callable[
    [Mapping[str, str], ExchangeTerms, Decimal, OwnerInventory], VenueNeeds | None
]

_START: dict[ExposureKind, _Start] = {
    ExposureKind.INVENTORY: start_ladder_needs,
    ExposureKind.POSITION: start_futures_needs,
}
_RESUME: dict[ExposureKind, _Resume] = {
    ExposureKind.INVENTORY: resume_ladder_needs,
    ExposureKind.POSITION: resume_futures_needs,
}


def start_needs_of(
    profile: VenueProfile,
    config: Mapping[str, str],
    terms: ExchangeTerms,
    price: Decimal,
) -> VenueNeeds | None:
    return _START[profile.exposure_kind](config, terms, price)


def resume_needs_of(
    profile: VenueProfile,
    config: Mapping[str, str],
    terms: ExchangeTerms,
    price: Decimal,
    inventory: OwnerInventory,
) -> VenueNeeds | None:
    return _RESUME[profile.exposure_kind](config, terms, price, inventory)
