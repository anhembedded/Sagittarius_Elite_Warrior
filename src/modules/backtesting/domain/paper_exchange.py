from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.fill_pricing import (
    FillPricing,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.open_position import (
    OpenPosition,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.fee_calculator_policy import (
    FeeCalculatorPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.order_matching_policy import (
    OrderMatchingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.position_lifecycle_policy import (
    PositionLifecyclePolicy,
    PositionOpenRequest,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.stop_management_policy import (
    StopManagementPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    ISizingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

logger = logging.getLogger("App.PaperExchange")

_EXIT_LOG_LABEL: dict[PositionSide, str] = {
    PositionSide.LONG: "SELL",
    PositionSide.SHORT: "COVER",
}


class PaperExchange:
    """
    @brief Simulated broker/exchange for backtesting strategy executions (BOT-021, BOT-041, BOT-050, BOT-104, EPIC-003C).
    @details The **books**: cash, open positions, the trade log, and the
    dispatch from a `Signal` to an entry or an exit. It records; it does not
    compute.

    Every number it records is asked of `FillPricing` (`fill_pricing.py`), which
    holds this run's configuration together with the four policies that do the
    arithmetic; a position is an `OpenPosition` (`open_position.py`). PR 3.1c-2
    split the three apart and `fill_pricing.py`'s docstring carries the
    argument. The constructor's four `FillPricing` policy parameters pass
    straight through unchanged: fifty-five inline call sites in this class's
    own test file construct it (`ONBOARDING` §8 trap 5). `StopManagementPolicy`
    (`stop_management_policy.py`) is a fifth, separate policy — not part of the
    `FillPricing` bundle, since it adjusts a position's risk state before a
    fill is ever considered, rather than computing one. `PositionLifecyclePolicy`
    (`position_lifecycle_policy.py`, `BOT-144`) is a sixth: the entry/exit/
    trade-recording mechanics themselves (`open_position()`/
    `close_one_position()`/`close_partial_position()`/
    `apply_partial_take_profits()`), extracted once this file crossed the
    400-line ceiling `architecture-rule.md` §5.4 sets — this class keeps
    owning `self._balance`/`self._positions`/`self._trades` (the actual
    books) and applies the deltas the policy returns; it does not hand the
    ledger itself to the policy.
    """

    def __init__(
        self,
        symbol: str,
        initial_balance: float,
        fee_percent: float = 0.1,
        position_sizing: PositionSizing | None = None,
        broker_config: BrokerSimulationConfig | None = None,
        margin_policy: MarginRiskPolicy | None = None,
        sizing_policy: ISizingPolicy | None = None,
        matching_policy: OrderMatchingPolicy | None = None,
        fee_policy: FeeCalculatorPolicy | None = None,
        stop_management_policy: StopManagementPolicy | None = None,
        lifecycle_policy: PositionLifecyclePolicy | None = None,
    ) -> None:
        if initial_balance <= 0:
            raise ValueError(f"initial_balance must be positive, got {initial_balance}")
        if fee_percent < 0:
            raise ValueError(f"fee_percent must be >= 0, got {fee_percent}")

        self._symbol = symbol
        self._balance = initial_balance
        self._initial_balance = initial_balance

        if broker_config is not None:
            self._broker_config = broker_config
        else:
            self._broker_config = BrokerSimulationConfig(
                commission_type=CommissionType.PERCENT,
                commission_value=fee_percent,
            )

        if position_sizing is not None:
            self._position_sizing = position_sizing
        else:
            self._position_sizing = PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY,
                value=100.0,
            )

        #: Every number this class records is asked of this object; the four
        #: `None` defaults are resolved there, once, rather than here.
        self._pricing = FillPricing(
            self._broker_config,
            self._position_sizing,
            margin_policy=margin_policy,
            sizing_policy=sizing_policy,
            matching_policy=matching_policy,
            fee_policy=fee_policy,
        )

        self._positions: list[OpenPosition] = []
        self._trades: list[Trade] = []
        #: Not part of the `FillPricing` bundle above — those four compute a
        #: fill's price/quantity; this one adjusts a position's risk state
        #: (MAE/MFE, break-even, trailing) BEFORE a fill is ever considered.
        self._stop_management = stop_management_policy or StopManagementPolicy()
        #: The entry/exit/trade-recording mechanics — see the class
        #: docstring. `symbol`/`self._broker_config`/`self._pricing` never
        #: change across a run, so this is safe to construct once here.
        self._lifecycle = lifecycle_policy or PositionLifecyclePolicy(
            symbol, self._pricing, self._broker_config
        )

        logger.info(
            f"[paper-exchange] Initialized for {symbol} | Initial Capital: {initial_balance:,.2f} | "
            f"Sizing: {self._position_sizing.type.value} ({self._position_sizing.value}) | "
            f"Pyramiding: {self._broker_config.pyramiding} | Slippage: {self._broker_config.slippage_ticks} ticks | "
            f"Commission: {self._broker_config.commission_value} ({self._broker_config.commission_type.value})"
        )

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def balance(self) -> float:
        """Available unallocated cash balance."""
        return self._balance

    @property
    def is_in_position(self) -> bool:
        return len(self._positions) > 0

    @property
    def position_count(self) -> int:
        return len(self._positions)

    @property
    def current_side(self) -> PositionSide | None:
        """BOT-110 — the side every currently open position shares, or None when flat."""
        return self._positions[0].side if self._positions else None

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)

    @property
    def position_sizing(self) -> PositionSizing:
        return self._position_sizing

    @property
    def broker_config(self) -> BrokerSimulationConfig:
        return self._broker_config

    def equity(self, mark_price: float) -> float:
        """Cash balance if flat, or cash balance plus marked-to-market position values."""
        if not self._positions:
            return self._balance
        total_open_value = sum(
            self._pricing.mark_to_market(
                pos.side,
                pos.leverage,
                pos.quantity,
                pos.entry_price,
                pos.balance_before_entry,
                mark_price,
            )
            for pos in self._positions
        )
        return self._balance + total_open_value

    def fill(self, signal: Signal, price: float, time: datetime) -> Trade | None:
        """
        Executes signal at price/time.
        Returns the last closed Trade on a SELL/COVER that closed positions, otherwise None.
        """
        if signal.action is SignalAction.BUY:
            self._open(PositionSide.LONG, price, time, signal.reason, signal.metadata)
            return None
        if signal.action is SignalAction.SELL:
            closed = self._close(
                PositionSide.LONG, price, time, ExitReason.STRATEGY_SIGNAL
            )
            return closed[-1] if closed else None
        if signal.action is SignalAction.SHORT:
            self._open(PositionSide.SHORT, price, time, signal.reason, signal.metadata)
            return None
        if signal.action is SignalAction.COVER:
            closed = self._close(
                PositionSide.SHORT, price, time, ExitReason.STRATEGY_SIGNAL
            )
            return closed[-1] if closed else None
        return None

    def force_close(self, price: float, time: datetime) -> Trade | None:
        """
        Realizes every still-open position, either side, at price/time at the end of a backtest run.
        """
        closed = list(
            self._close(PositionSide.LONG, price, time, ExitReason.END_OF_BACKTEST)
        )
        closed += self._close(
            PositionSide.SHORT, price, time, ExitReason.END_OF_BACKTEST
        )
        return closed[-1] if closed else None

    def _open(
        self,
        side: PositionSide,
        price: float,
        time: datetime,
        reason: str,
        metadata: Mapping[str, Any],
    ) -> None:
        request = PositionOpenRequest(
            side=side, price=price, time=time, reason=reason, metadata=metadata
        )
        self._positions, self._balance = self._lifecycle.open_position(
            self._positions, self._balance, request
        )

    def _close(
        self,
        side: PositionSide,
        price: float,
        time: datetime,
        exit_reason: ExitReason,
    ) -> Sequence[Trade]:
        matching = [pos for pos in self._positions if pos.side is side]
        if not matching:
            logger.debug(
                f"[paper-exchange] {_EXIT_LOG_LABEL[side]} rejected: no open "
                f"{side.value} positions to close"
            )
            return []

        effective_price = self._pricing.exit_effective_price(side, price)
        slippage_delta = self._pricing.slippage_delta()

        closed_trades: list[Trade] = []
        for pos in matching:
            trade, balance_release = self._lifecycle.close_one_position(
                pos,
                effective_price,
                time,
                exit_reason,
                raw_price=price,
                slippage_delta=slippage_delta,
            )
            closed_trades.append(trade)
            self._balance += balance_release
        self._trades.extend(closed_trades)

        self._positions = [pos for pos in self._positions if pos.side is not side]
        logger.debug(
            f"[paper-exchange] All positions closed "
            f"({len(closed_trades)} trades) | New Balance: {self._balance:,.2f}"
        )
        return closed_trades

    def check_intrabar_stops(
        self,
        high: float,
        low: float,
        time: datetime,
        magnifier_lookup: Callable[[], Sequence[tuple[float, float]]] | None = None,
    ) -> Sequence[Trade]:
        """
        @brief Widens every open position's MAE/MFE from this bar, arms
        break-even stops (`BOT-105A`) then ratchets trailing stops
        (`BOT-105A`), then checks liquidation/stop-loss/take-profit
        against the same high/low.
        @details Liquidation is checked **first** and its trades removed from
        `self._positions` before stop-loss/take-profit ever sees them
        (`BOT-049` §2) — a real exchange liquidates before a user's own SL/TP
        order could fill, so a position that would hit both in one bar must
        close as `LIQUIDATION`, never `STOP_LOSS`/`TAKE_PROFIT`. A break-even
        or trailing-stop move happens from this same bar's high/low, so a bar
        that both triggers one and reverses far enough can close as
        `STOP_LOSS` at the new stop within that one bar — and
        `magnifier_lookup` (`BOT-105B`) is passed down only after both moves,
        so an ambiguous SL+TP bar is resolved against the position's real,
        post-adjustment stop price, never a stale pre-arm one. Partial
        take-profit (`BOT-105C`) is checked **last**, against whatever
        survives liquidation/stop-loss/take-profit this bar — a position
        already fully closed by one of those never also produces a
        partial-TP trade the same bar.
        """
        if not self._positions:
            return []

        self._stop_management.update_excursion_tracking(
            self._positions, self._pricing, high, low
        )
        self._stop_management.apply_break_even_stops(
            self._positions, self._broker_config.break_even_trigger_pct
        )
        self._stop_management.apply_trailing_stops(
            self._positions,
            self._broker_config.trailing_activation_pct,
            self._broker_config.trailing_offset_pct,
            high,
            low,
        )

        liquidated, still_open = self._pricing.evaluate_liquidations(
            self._positions, high, low
        )
        self._positions = still_open

        triggered, still_open = self._pricing.evaluate_intrabar_stops(
            self._positions, high, low, magnifier_lookup
        )
        self._positions = still_open

        all_triggered = liquidated + triggered
        closed_trades: list[Trade] = []
        for pos, exit_price, reason in all_triggered:
            trade, balance_release = self._lifecycle.close_one_position(
                pos, exit_price, time, reason
            )
            closed_trades.append(trade)
            self._balance += balance_release
        self._trades.extend(closed_trades)

        partial_trades, partial_balance_release, self._positions = (
            self._lifecycle.apply_partial_take_profits(self._positions, high, low, time)
        )
        self._balance += partial_balance_release
        self._trades.extend(partial_trades)
        return [*closed_trades, *partial_trades]
