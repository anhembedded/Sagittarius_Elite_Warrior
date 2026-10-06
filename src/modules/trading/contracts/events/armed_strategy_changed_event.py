"""`EPIC-033K` stage 3 — a venue's armed strategy changed.

@details Arming moved from the Trade mode's Strategy panel to the Bots mode,
while the Trade mode's chart still draws the armed strategy's lines for its
venue. Two screens wanting one truth is the bus's job
(`architecture-rule.md` §6): the strategy module's arm and disarm handlers
publish this after an arm or a disarm takes effect, and each reader re-reads
`IArmedStrategyReader` for its venue. The event carries no config, so a
reader never holds a second copy that could disagree with the session's.

Declared in `trading/contracts/`, as `IArmedStrategyReader` is: `trading` may
not import `strategy`'s contracts, and `strategy` already imports these
(`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8).

@par Not `frozen` — the same `BaseEvent` inheritance cost
`TradingSwitchChangedEvent` documents. Treat as read-only by convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class ArmedStrategyChangedEvent(BaseEvent):
    """@brief A strategy was armed or disarmed on `venue`."""

    #: Whether a strategy is armed on `venue` now.
    armed: bool
    #: The venue whose armed strategy changed. No default, as on every
    #: venue-scoped event (`EPIC-028C`).
    venue: TradingVenue = field(kw_only=True)
