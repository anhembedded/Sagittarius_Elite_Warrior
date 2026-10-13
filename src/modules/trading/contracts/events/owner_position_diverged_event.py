from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class OwnerPositionDivergedEvent(BaseEvent):
    """
    @brief Domain event (`EPIC-039D`): the position `positionRisk` reports on
    a budgeted owner's symbol differs from the one derived from its tagged
    fills, by more than one step.

    @details Published once per cause (the same two figures are not reported
    again until they agree). `divergence.kind` says whether the owner's own
    fills explain nothing (`POSITION_MISMATCH`) or the exchange moved with no
    tagged fill since they last agreed (`POSITION_CHANGED_UNORDERED`: a forced
    close, an ADL, a trade by hand), which `EPIC-039F`'s guard consumes.

    @par Not `frozen` - same `BaseEvent` inheritance cost the position events
    document. Treat as read-only by convention.
    """

    divergence: PositionDivergence
    venue: TradingVenue = field(kw_only=True)
