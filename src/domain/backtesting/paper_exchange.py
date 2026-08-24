from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.fee_calculator_policy import (
    FeeCalculatorPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.order_matching_policy import (
    OrderMatchingPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

logger = logging.getLogger("App.PaperExchange")

_ENTRY_LOG_LABEL: dict[PositionSide, str] = {
    PositionSide.LONG: "BUY",
    PositionSide.SHORT: "SHORT",
}
_EXIT_LOG_LABEL: dict[PositionSide, str] = {
    PositionSide.LONG: "SELL",
    PositionSide.SHORT: "COVER",
}


@dataclass
class _OpenPosition:
    quantity: float
    entry_price: float
    entry_time: datetime
    balance_before_entry: float
    entry_fee: float
    entry_reason: str
    entry_metadata: Mapping[str, Any] = field(default_factory=dict)
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    side: PositionSide = PositionSide.LONG
    leverage: float = 1.0


class PaperExchange:
    """
    @brief Simulated broker/exchange for backtesting strategy executions (BOT-021, BOT-041, BOT-050, BOT-104, EPIC-003C).
    @details Orchestrates trade lifecycle, delegating financial calculations to pure Domain Policies:
    - MarginRiskPolicy: margin, leverage, mark-to-market, realized PnL
    - OrderMatchingPolicy: slippage, effective entry/exit prices, intrabar stops
    - FeeCalculatorPolicy: commission calculation on notional/contracts
    """

    def __init__(
        self,
        symbol: str,
        initial_balance: float,
        fee_percent: float = 0.1,
        position_sizing: PositionSizing | None = None,
        broker_config: BrokerSimulationConfig | None = None,
        margin_policy: MarginRiskPolicy | None = None,
        matching_policy: OrderMatchingPolicy | None = None,
        fee_policy: FeeCalculatorPolicy | None = None,
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

        self._margin_policy = margin_policy or MarginRiskPolicy()
        self._matching_policy = matching_policy or OrderMatchingPolicy()
        self._fee_policy = fee_policy or FeeCalculatorPolicy()

        self._positions: list[_OpenPosition] = []
        self._trades: list[Trade] = []

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
            self._margin_policy.mark_to_market(
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

    def _slippage_delta(self) -> float:
        return self._matching_policy.calculate_slippage_delta(
            self._broker_config.slippage_ticks, self._broker_config.tick_size
        )

    def _entry_effective_price(self, side: PositionSide, price: float) -> float:
        return self._matching_policy.calculate_entry_effective_price(
            side, price, self._slippage_delta()
        )

    def _exit_effective_price(self, side: PositionSide, price: float) -> float:
        return self._matching_policy.calculate_exit_effective_price(
            side, price, self._slippage_delta()
        )

    def _leverage_for(self, side: PositionSide) -> float:
        return self._margin_policy.get_leverage(
            side,
            self._broker_config.long_leverage,
            self._broker_config.short_leverage,
        )

    def _calculate_entry_capital(
        self, side: PositionSide, price: float, current_equity: float
    ) -> tuple[float, float, float]:
        effective_price = self._entry_effective_price(side, price)
        if effective_price <= 0:
            return 0.0, 0.0, 0.0

        leverage = self._leverage_for(side)
        margin, notional_capital = self._margin_policy.calculate_margin_and_notional(
            side,
            effective_price,
            current_equity,
            self._balance,
            self._position_sizing,
            leverage,
            self._broker_config.stop_loss_pct,
        )

        if margin <= 0 or notional_capital <= 0:
            return 0.0, 0.0, 0.0

        entry_fee, quantity = self._fee_policy.calculate_entry_fee_and_quantity(
            notional_capital,
            effective_price,
            self._broker_config.commission_type,
            self._broker_config.commission_value,
        )

        if quantity <= 0:
            return 0.0, 0.0, 0.0

        return margin, quantity, entry_fee

    def _open(
        self,
        side: PositionSide,
        price: float,
        time: datetime,
        reason: str,
        metadata: Mapping[str, Any],
    ) -> None:
        opposite = (
            PositionSide.SHORT if side is PositionSide.LONG else PositionSide.LONG
        )
        if any(pos.side is opposite for pos in self._positions):
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: an opposite-side "
                f"({opposite.value}) position is still open — BOT-050 requires the "
                "strategy to close it first with an explicit signal, never an implicit reversal"
            )
            return
        if len(self._positions) >= self._broker_config.pyramiding:
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: pyramiding limit "
                f"reached ({len(self._positions)}/{self._broker_config.pyramiding})"
            )
            return

        current_eq = self.equity(price)
        capital_deployed, quantity, entry_fee = self._calculate_entry_capital(
            side, price, current_eq
        )
        if quantity <= 0 or capital_deployed <= 0:
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: insufficient balance "
                f"({self._balance:,.2f}) for sizing {self._position_sizing}"
            )
            return

        effective_price = self._entry_effective_price(side, price)
        stop_loss_price = self._matching_policy.calculate_stop_loss_price(
            side, effective_price, self._broker_config.stop_loss_pct
        )
        take_profit_price = self._matching_policy.calculate_take_profit_price(
            side, effective_price, self._broker_config.take_profit_pct
        )

        self._balance -= capital_deployed
        position = _OpenPosition(
            quantity=quantity,
            entry_price=effective_price,
            entry_time=time,
            balance_before_entry=capital_deployed,
            entry_fee=entry_fee,
            entry_reason=reason,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            entry_metadata=metadata,
            side=side,
            leverage=self._leverage_for(side),
        )
        self._positions.append(position)
        slippage_delta = self._slippage_delta()
        slip_sign = "+" if side is PositionSide.LONG else "-"
        logger.debug(
            f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} filled | Price: {effective_price:,.2f} "
            f"(raw: {price:,.2f}, slip: {slip_sign}{slippage_delta:,.2f}) | "
            f"Qty: {quantity:.6f} | Cost: {capital_deployed:,.2f} | Fee: {entry_fee:,.2f} | "
            f"Pos: {len(self._positions)}/{self._broker_config.pyramiding} | Cash Left: {self._balance:,.2f}"
        )

    def _close_one_position(
        self,
        pos: _OpenPosition,
        exit_price: float,
        time: datetime,
        exit_reason: ExitReason,
        *,
        raw_price: float | None = None,
        slippage_delta: float = 0.0,
    ) -> Trade:
        exit_fee = self._fee_policy.calculate_exit_fee(
            pos.quantity,
            exit_price,
            self._broker_config.commission_type,
            self._broker_config.commission_value,
        )

        pnl, pnl_percent, balance_release = self._margin_policy.calculate_realized_pnl(
            pos.side,
            pos.leverage,
            pos.quantity,
            pos.entry_price,
            exit_price,
            pos.balance_before_entry,
            pos.entry_fee,
            exit_fee,
        )
        self._balance += balance_release

        trade = Trade(
            symbol=self._symbol,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=time,
            exit_price=exit_price,
            quantity=pos.quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            fees_paid=pos.entry_fee + exit_fee,
            entry_reason=pos.entry_reason,
            exit_reason=exit_reason,
            metadata=pos.entry_metadata,
            side=pos.side,
        )
        self._trades.append(trade)
        exit_label = _EXIT_LOG_LABEL[pos.side]
        if raw_price is not None:
            slip_sign = "-" if pos.side is PositionSide.LONG else "+"
            price_detail = (
                f"Price: {exit_price:,.2f} (raw: {raw_price:,.2f}, "
                f"slip: {slip_sign}{slippage_delta:,.2f})"
            )
        else:
            price_detail = f"Price: {exit_price:,.2f}"
        logger.debug(
            f"[paper-exchange] {exit_label} filled | {price_detail} | "
            f"Qty: {pos.quantity:.6f} | PnL: {pnl:+,.2f} ({pnl_percent:+.2f}%) | "
            f"Fee: {pos.entry_fee + exit_fee:,.2f} | Reason: {exit_reason.value}"
        )
        return trade

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

        effective_price = self._exit_effective_price(side, price)
        slippage_delta = self._slippage_delta()

        closed_trades = [
            self._close_one_position(
                pos,
                effective_price,
                time,
                exit_reason,
                raw_price=price,
                slippage_delta=slippage_delta,
            )
            for pos in matching
        ]

        self._positions = [pos for pos in self._positions if pos.side is not side]
        logger.debug(
            f"[paper-exchange] All positions closed "
            f"({len(closed_trades)} trades) | New Balance: {self._balance:,.2f}"
        )
        return closed_trades

    def check_intrabar_stops(
        self, high: float, low: float, time: datetime
    ) -> Sequence[Trade]:
        """
        @brief Checks every open position's stop-loss/take-profit against bar high/low boundaries.
        """
        if not self._positions:
            return []

        triggered, still_open = self._matching_policy.evaluate_intrabar_stops(
            self._positions, high, low
        )

        if not triggered:
            return []

        self._positions = still_open
        return [
            self._close_one_position(pos, exit_price, time, reason)
            for pos, exit_price, reason in triggered
        ]
