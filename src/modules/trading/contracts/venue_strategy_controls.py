"""`EPIC-028K` — one venue's live strategy, as a desk arms and reads it.

@details `IStrategyArmingControl` and `IArmedStrategyReader` are bound to the
primary venue for the single Trading screen and the Dev Board. Each desk
shows one venue and must arm, disarm and read that venue's strategy, and no
other's: the Spot desk arming through the primary (Futures) arming would arm
Futures. This bundle carries both ports already bound to `venue`, the way
`VenueTradingPorts` carries a venue's trading ports.

Plausible extensions, each one field here and one line in the strategy
module's adapter: a venue's chart overlay once overlays differ per venue; a
venue's own catalog if a strategy ever declares which markets it supports.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_armed_strategy_reader import (
    IArmedStrategyReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class VenueStrategyControls:
    """The live strategy ports of one venue, each already bound to `venue`."""

    venue: TradingVenue
    arming: IStrategyArmingControl
    armed: IArmedStrategyReader
