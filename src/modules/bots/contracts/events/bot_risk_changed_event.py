"""`EPIC-039F` - a running position bot's distance to liquidation changed level.

The typed fact the alert module reads (`LIQUIDATION_RISK`, `EPIC-036B`): a source reads
`level`, never the bot's state, and needs no timer of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import RiskLevel
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotRiskChangedEvent(BaseEvent):
    """
    @brief Published when the risk level of a running position bot changes: once per
    transition, never per beat. The return to `SAFE` is an event too, and re-arms the next
    warning.

    @details `liquidation_price` and `mark_price` are the exchange's reported figures at the
    reading that changed the level; `distance` is |mark - liquidation| / mark, `None` when it
    could not be measured (`UNKNOWN`). Published from the bot's worker thread, so a consumer
    marshals itself.

    @par Not `frozen` - the same `BaseEvent` inheritance cost `BotRangeChangedEvent` documents.
    Treat as read-only by convention.
    """

    bot_id: str
    symbol: str
    level: RiskLevel
    reason: str
    distance: Decimal | None
    mark_price: Decimal | None
    liquidation_price: Decimal | None
