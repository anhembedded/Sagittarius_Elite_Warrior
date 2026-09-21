"""Every number the paper broker needs before it may touch its books.

## Why this is a file and not five more methods on `PaperExchange`

`architecture-rule.md` §5 rule 4 caps a file at 400 lines; `paper_exchange.py`
was **472** and `EPIC-025D` §5.5 recorded the split as PR 3.1c's, naming the
seam: *"a broker's books, and the matching/fee/margin policies it delegates
to"*. The ceiling is what made it urgent, but the ceiling is not the argument —
a file can be short and still hold two abstraction levels, and this one held two
plainly:

  · **Arithmetic against the configuration.** What is the effective price after
    slippage, what leverage does this side get, how much capital may this entry
    use, what is the fee, what did this position realize, did a stop trigger
    inside the bar. Every answer is a number derived from
    `BrokerSimulationConfig`, `PositionSizing` and the four policies. Nothing
    here reads or writes a balance, a position list or a trade log.
  · **The books.** Cash, open positions, the trade log, and the dispatch from a
    `Signal` to an entry or an exit. It *records*; it does not compute.

`code/quality.md` §3's Single-Scope Cohesion is what a reader will reach
for to argue they belong together, and §5 rule 3 is the clause that wins here:
the two have the same *feature* but not the same *abstraction level*, and one of
them changes for a reason the other does not. A second sizing rule (ADR D17
promises the user an ATR-based one) or a venue with a different fee shape
changes this class and leaves the books alone; pyramiding, or a partial close,
changes the books and leaves this class alone.

## It is a holder, not a new rule

Not one formula moved. `MarginRiskPolicy`, `OrderMatchingPolicy`,
`FeeCalculatorPolicy` and `ISizingPolicy` still do the computing exactly as they
did — this class holds them together with the run's configuration so that a
caller asks in the vocabulary of a fill (*"what capital may a LONG entry at this
price use?"*) rather than assembling four arguments from two configuration
objects at each of five call sites. That is the same shape `StrategyEngineFactory`
took in PR 3.1b and for the same measured reason.

`EPIC-025D` §2's criterion for this phase is a **bit-identical** trade log, so
every method below is the body it had as a `PaperExchange` private method, moved
and made public to its one caller.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import PositionSizing
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.fee_calculator_policy import (
    FeeCalculatorPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.order_matching_policy import (
    IStoppablePosition,
    OrderMatchingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    ISizingPolicy,
    default_sizing_policy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


class FillPricing:
    """The four policies bound to one run's configuration."""

    def __init__(
        self,
        broker_config: BrokerSimulationConfig,
        position_sizing: PositionSizing,
        margin_policy: MarginRiskPolicy | None = None,
        sizing_policy: ISizingPolicy | None = None,
        matching_policy: OrderMatchingPolicy | None = None,
        fee_policy: FeeCalculatorPolicy | None = None,
    ) -> None:
        self._broker_config = broker_config
        self._position_sizing = position_sizing
        self._margin_policy = margin_policy or MarginRiskPolicy()
        #: The sizing half of what `MarginRiskPolicy` used to do — `strategy`'s
        #: since PR 2.1d (ADR D17), reached through its published port. The
        #: default comes from `contracts/default_sizing_policy()` rather than
        #: across the boundary, which is what retired this module's last
        #: allowlist entry to `strategy`'s internals; it stays a default because
        #: `PaperExchange`'s constructor has fifty-five inline call sites in its
        #: own test file (`ONBOARDING` §8 trap 5), while the backtest handlers
        #: pass the resolved port so a second rule reaches a real backtest.
        #: Full account: `EPIC-025D` §5.2.
        self._sizing_policy = sizing_policy or default_sizing_policy()
        self._matching_policy = matching_policy or OrderMatchingPolicy()
        self._fee_policy = fee_policy or FeeCalculatorPolicy()

    # -- prices ------------------------------------------------------------

    def slippage_delta(self) -> float:
        return self._matching_policy.calculate_slippage_delta(
            self._broker_config.slippage_ticks, self._broker_config.tick_size
        )

    def entry_effective_price(self, side: PositionSide, price: float) -> float:
        return self._matching_policy.calculate_entry_effective_price(
            side, price, self.slippage_delta()
        )

    def exit_effective_price(self, side: PositionSide, price: float) -> float:
        return self._matching_policy.calculate_exit_effective_price(
            side, price, self.slippage_delta()
        )

    def stop_loss_price(
        self, side: PositionSide, effective_price: float
    ) -> float | None:
        return self._matching_policy.calculate_stop_loss_price(
            side, effective_price, self._broker_config.stop_loss_pct
        )

    def take_profit_price(
        self, side: PositionSide, effective_price: float
    ) -> float | None:
        return self._matching_policy.calculate_take_profit_price(
            side, effective_price, self._broker_config.take_profit_pct
        )

    def evaluate_intrabar_stops[TPosition: IStoppablePosition](
        self, positions: Sequence[TPosition], high: float, low: float
    ) -> tuple[list[tuple[TPosition, float, ExitReason]], list[TPosition]]:
        """Generic in the position type, like the policy it delegates to: the
        caller's own `OpenPosition` comes back as an `OpenPosition`, so
        `self._positions` stays precisely typed rather than widening to the
        contract on every bar."""
        return self._matching_policy.evaluate_intrabar_stops(positions, high, low)

    # -- leverage and sizing ----------------------------------------------

    def leverage_for(self, side: PositionSide) -> float:
        return self._margin_policy.get_leverage(
            side,
            self._broker_config.long_leverage,
            self._broker_config.short_leverage,
        )

    def entry_capital(
        self,
        side: PositionSide,
        price: float,
        current_equity: float,
        available_balance: float,
    ) -> tuple[float, float, float]:
        """`(margin, quantity, entry_fee)`, or three zeros when this entry is
        not fundable — which is the *one* refusal a caller must handle, and the
        reason all three come back together rather than through three calls that
        could disagree about whether the entry happens at all."""
        effective_price = self.entry_effective_price(side, price)
        if effective_price <= 0:
            return 0.0, 0.0, 0.0

        leverage = self.leverage_for(side)
        allocation = self._sizing_policy.allocate(
            sizing=self._position_sizing,
            effective_price=effective_price,
            current_equity=current_equity,
            available_balance=available_balance,
            leverage=leverage,
            stop_loss_pct=self._broker_config.stop_loss_pct,
        )

        if not allocation.is_fundable:
            return 0.0, 0.0, 0.0

        entry_fee, quantity = self._fee_policy.calculate_entry_fee_and_quantity(
            allocation.notional_capital,
            effective_price,
            self._broker_config.commission_type,
            self._broker_config.commission_value,
        )

        if quantity <= 0:
            return 0.0, 0.0, 0.0

        return allocation.margin, quantity, entry_fee

    # -- what a position is worth, and what it realized --------------------

    def mark_to_market(
        self,
        side: PositionSide,
        leverage: float,
        quantity: float,
        entry_price: float,
        balance_before_entry: float,
        mark_price: float,
    ) -> float:
        return self._margin_policy.mark_to_market(
            side, leverage, quantity, entry_price, balance_before_entry, mark_price
        )

    def exit_fee(self, quantity: float, exit_price: float) -> float:
        return self._fee_policy.calculate_exit_fee(
            quantity,
            exit_price,
            self._broker_config.commission_type,
            self._broker_config.commission_value,
        )

    def realized_pnl(
        self,
        side: PositionSide,
        leverage: float,
        quantity: float,
        entry_price: float,
        exit_price: float,
        balance_before_entry: float,
        entry_fee: float,
        exit_fee: float,
    ) -> tuple[float, float, float]:
        """`(pnl, pnl_percent, balance_release)` — the third is what the books
        add back to cash, and it is the only one of the three they *act* on."""
        return self._margin_policy.calculate_realized_pnl(
            side,
            leverage,
            quantity,
            entry_price,
            exit_price,
            balance_before_entry,
            entry_fee,
            exit_fee,
        )
