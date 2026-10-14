"""`EPIC-039E` — which readiness rules judge a venue: chosen by its profile (decision D1).

@details `judge_venue` is the one door the readiness path uses once it holds a
`VenueSnapshot`: it reads the venue profile's `exposure_kind` and runs that kind's rules, so
the Spot rules (`exchange_rules.RULES`) and the Futures rules (`futures_rules.FUTURES_RULES`)
never see each other's facts and no rule branches on a market. A snapshot of the other
profile, or needs of the other profile, is a wiring defect and raises
`WrongVenueFactsError` rather than being judged as if it were empty.

Extension cases: a third exposure kind is one row in `_JUDGES`.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.exchange_rules import (
    RuleOutcome,
    RunPurpose,
    judge_exchange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_rules import (
    judge_futures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    VenueProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_needs import (
    FuturesNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_needs import (
    LadderNeeds,
)

type VenueNeeds = LadderNeeds | FuturesNeeds


class WrongVenueFactsError(TypeError):
    """Facts or needs of one profile reached the rules of another."""


def judge_venue(
    profile: VenueProfile,
    snapshot: VenueSnapshot,
    needs: VenueNeeds | None,
    purpose: RunPurpose,
) -> RuleOutcome:
    return _JUDGES[profile.exposure_kind](snapshot, needs, purpose)


def _judge_inventory(
    snapshot: VenueSnapshot, needs: VenueNeeds | None, purpose: RunPurpose
) -> RuleOutcome:
    if isinstance(snapshot, FuturesLoaded) or isinstance(needs, FuturesNeeds):
        raise WrongVenueFactsError("an inventory venue was handed Futures facts")
    return judge_exchange(snapshot, needs, purpose)


def _judge_position(
    snapshot: VenueSnapshot, needs: VenueNeeds | None, purpose: RunPurpose
) -> RuleOutcome:
    if isinstance(snapshot, ExchangeLoaded) or isinstance(needs, LadderNeeds):
        raise WrongVenueFactsError("a position venue was handed Spot facts")
    return judge_futures(snapshot, needs, purpose)


type _Judge = Callable[[VenueSnapshot, VenueNeeds | None, RunPurpose], RuleOutcome]

_JUDGES: dict[ExposureKind, _Judge] = {
    ExposureKind.INVENTORY: _judge_inventory,
    ExposureKind.POSITION: _judge_position,
}
