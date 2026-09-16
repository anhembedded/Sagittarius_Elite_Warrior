"""`MarginSizingPolicy` — `ISizingPolicy` as this app computes it today
(ADR D17, `EPIC-025` PR 2.1d).

@details The formula is `MarginRiskPolicy.calculate_margin_and_notional()`'s,
unchanged (`BOT-104`, `BOT-041`) — this module is where it now lives, not a
rewrite of it. It moved because of what owns it, not because of what it
computes: the rule sat in `domain/backtesting/policies/` while `trading`'s
`position_sizing_bridge` imported it, which made `trading` depend on
`backtesting` — a dependency the context map (HLD §2.1) forbids and that no
diagram in this repository ever drew. ADR D17 answered the question the
allowlist entry had been holding open since Phase 1: *how much to bet* is the
armed strategy's decision, so `strategy` owns it and both callers ask it.

`MarginRiskPolicy` stays in `backtesting` with the rest of what it does —
leverage by direction, mark-to-market valuation and PnL realization. Those are
a paper broker's books, not a sizing rule, and they are the reason this is a
split rather than a move of the whole file: Phase 3 turns `backtesting` into a
module, and a `modules/backtesting` reaching into `modules/strategy` for
`calculate_realized_pnl` would be the same wrong-direction import again, one
context over.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    NO_ALLOCATION,
    ISizingPolicy,
    MarginAllocation,
)

logger = logging.getLogger("App.MarginSizingPolicy")


class MarginSizingPolicy(ISizingPolicy):
    """@brief Allocates capital by `PositionSizing`, then clamps the margin to
    what the account actually has free."""

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
        """@brief See `ISizingPolicy.allocate`.
        @details
        - PERCENT_OF_EQUITY / FIXED_CASH: leverage scales margin into larger
          notional capital.
        - FIXED_CONTRACTS / RISK_PERCENT: leverage reduces the margin required
          for the fixed contract count/risk.
        Clamps margin to the available liquid balance while preserving the
        exact leverage ratio.
        """
        if effective_price <= 0 or leverage <= 0:
            return NO_ALLOCATION

        sizing_type = sizing.type
        sizing_val = sizing.value

        if sizing_type is PositionSizingType.PERCENT_OF_EQUITY:
            margin = current_equity * (sizing_val / 100.0)
            notional_capital = margin * leverage
        elif sizing_type is PositionSizingType.FIXED_CASH:
            margin = sizing_val
            notional_capital = margin * leverage
        elif sizing_type is PositionSizingType.FIXED_CONTRACTS:
            notional_capital = sizing_val * effective_price
            margin = notional_capital / leverage
        elif sizing_type is PositionSizingType.RISK_PERCENT:
            if stop_loss_pct is None or stop_loss_pct <= 0:
                # Names the sizing that could not be honoured rather than the
                # direction of the order, which never entered the formula —
                # see `ISizingPolicy`'s docstring on the absent `side`.
                logger.debug(
                    "[sizing] %s rejected: it needs a stop-loss distance "
                    "(BrokerSimulationConfig.stop_loss_pct) to size against.",
                    sizing_type.value,
                )
                return NO_ALLOCATION
            stop_distance = effective_price * (stop_loss_pct / 100.0)
            if stop_distance <= 0:
                return NO_ALLOCATION
            risk_amount = current_equity * (sizing_val / 100.0)
            notional_capital = risk_amount * (effective_price / stop_distance)
            margin = notional_capital / leverage
        else:
            margin = available_balance
            notional_capital = margin * leverage

        if margin > available_balance:
            scale = (available_balance / margin) if margin > 0 else 0.0
            margin = available_balance
            notional_capital *= scale

        allocation = MarginAllocation(margin=margin, notional_capital=notional_capital)
        if not allocation.is_fundable:
            return NO_ALLOCATION
        return allocation
