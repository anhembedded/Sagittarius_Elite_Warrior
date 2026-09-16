"""`ISizingPolicy` (ADR D17) — the one rule that answers *how much to bet*.

@details Position size is a **strategy** decision, not an exchange one:
`LiveStrategyConfig` already carries the sizing percent and the leverage the
user armed with, and `backtesting` must size a paper fill by the same rule or a
backtest stops predicting the live bot. So the rule lives here, published, and
its two consumers call the same method — which is what ADR D17 means by
*"backtest and live sizes are one number by construction"*.

What this port deliberately does **not** do is anything exchange-specific.
`trading` owns the lot and tick filters and `TradingLimitPolicy`; this returns
capital, in the account's own currency, and the caller turns it into a quantity
the exchange will accept. ADR D17 draws the line there, and it is why `side`
is absent from the signature: direction changes which filters and which limits
apply, and it changes nothing at all about how much capital a rule allocates.
(The rule that moved here took a `side` and used it for one word in one debug
line, while `position_sizing_bridge` passed a fixed `LONG` "regardless of which
direction this order actually is" — a parameter a published contract would have
been promising to honour.)

**Never raises.** An input that cannot fund an order — a non-positive price, no
leverage, a `RISK_PERCENT` sizing with no stop distance to measure risk against
— answers with an allocation that is not fundable. A caller treats that as
*nothing to send*, which is a normal outcome of a signal arriving on an empty
account, not an error to handle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import PositionSizing


@dataclass(frozen=True, slots=True)
class MarginAllocation:
    """@brief The capital one order may use: what it locks, and what it buys.

    @details Two numbers rather than one because leverage separates them —
    `notional_capital` is the position's size at the exchange and `margin` is
    what it actually costs the account. A paper fill books the margin and sizes
    the position off the notional; a live order only needs the notional. They
    were a bare `tuple[float, float]` while the rule was internal to
    `backtesting`, which `architecture-rule.md` §2.1 does not allow a published
    contract to be.
    """

    margin: float
    notional_capital: float

    @property
    def is_fundable(self) -> bool:
        """@brief Whether this allocation can pay for an order at all.

        @details The named decision, so that neither caller re-types
        `margin <= 0 or notional_capital <= 0` and neither has to know that
        *both* have to be positive — the clamp to the available balance can
        scale a notional to nothing while the margin still looks paid for.
        """
        return self.margin > 0 and self.notional_capital > 0


#: The answer to "this cannot be funded", so an implementation returns a value
#: with a name rather than two zeros a reader has to interpret.
NO_ALLOCATION = MarginAllocation(margin=0.0, notional_capital=0.0)


class ISizingPolicy(ABC):
    """@brief How much capital one order may use, by the armed strategy's own
    sizing rule."""

    @abstractmethod
    def allocate(
        self,
        *,
        sizing: PositionSizing,
        effective_price: float,
        current_equity: float,
        available_balance: float,
        leverage: float,
        stop_loss_pct: float | None = None,
    ) -> MarginAllocation:
        """@brief Allocates capital for one order.

        @param sizing What the user chose: a percentage of equity, a fixed
        cash amount, a fixed contract count, or a risk percentage.
        @param effective_price The price the order is expected to fill at —
        slippage already applied by the caller, because who applies slippage
        differs between a paper fill and a live order.
        @param current_equity Account value including open positions; what a
        percentage-of-equity sizing is a percentage *of*.
        @param available_balance Free balance. The allocated margin is clamped
        to it, so a sizing the account cannot afford shrinks instead of being
        refused.
        @param leverage The armed leverage, as a multiplier.
        @param stop_loss_pct The stop distance as a percentage of the entry
        price. Only `RISK_PERCENT` sizing needs it — it is the distance that
        turns "risk 1% of equity" into a position size — and that sizing is
        not fundable without it.
        @return An allocation; `is_fundable` is `False` when the inputs cannot
        pay for an order. Keyword-only: six numbers in a row is an argument
        order a caller gets wrong silently.
        """
        ...
