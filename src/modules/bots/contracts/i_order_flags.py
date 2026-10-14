"""`EPIC-039H` — the flags a Grid's ladder orders carry, per venue profile.

@details A counter order of a position venue exits the position the ladder built, so it is sent
reduce-only: the exchange then refuses one that would flip or grow the position (`-2022`),
which a ladder out of step with its position must see as a refusal, never as a new position.
Spot has no such flag. Post-only is not used on any venue (decision O10, `EPIC-039`).

Plausible extensions, each a local change: SHORT's BUYs are reduce-only and NEUTRAL's orders
are not (`EPIC-039I`), one more branch of the position implementation; post-only, once Binance's
`GTX` semantics are confirmed, is a second method here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


class IOrderFlags(ABC):
    @abstractmethod
    def reduce_only(self, side: OrderSide) -> bool:
        """Whether a ladder order on `side` may only reduce the position."""
