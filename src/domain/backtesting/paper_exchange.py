import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
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

#: Log-message verbs — deliberately mirror the SignalAction names (BUY/SELL/
#: SHORT/COVER), not PositionSide's own values ("long"/"short"), so a LONG
#: entry keeps logging "BUY filled" exactly as it always has (existing tests
#: grep for that literal substring) instead of becoming "LONG filled".
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
    #: BOT-041 — absolute prices computed once at entry from
    #: `BrokerSimulationConfig.stop_loss_pct`/`take_profit_pct`. `None` when
    #: the corresponding config field is `None` (feature off for this run).
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    #: BOT-050 — LONG for every position before this field existed.
    side: PositionSide = PositionSide.LONG


class PaperExchange:
    """
    @brief Simulated broker/exchange for backtesting strategy executions (BOT-021, BOT-041, BOT-050, BOT-104).

    @details
    Supports:
    1. Flexible Position Sizing: Percent of Equity, Fixed Cash, Fixed Contracts, or Risk Percent.
    2. Pyramiding: Up to N concurrent entries in the same direction.
    3. Slippage Simulation: Configurable tick slippage applied to market fills.
    4. Flexible Commission Models: Percentage of notional, Fixed cash per order, or Fixed cash per contract.
    5. Stop-Loss / Take-Profit: optional per-run % thresholds, checked every
       bar via `check_intrabar_stops()` — callers must call it every bar,
       not only when a signal fires.
    6. Short-Selling: `SignalAction.SHORT`/`COVER` open/close a SHORT
       position — mirrors LONG's PnL/SL-TP/sizing math with entry/exit and
       stop/target roles reversed. A strategy owns reversal explicitly (two
       signals, e.g. SELL then SHORT); this exchange never infers one from
       position state, and rejects an opposite-side entry while one side is
       already open rather than silently mixing them.
    """

    def __init__(
        self,
        symbol: str,
        initial_balance: float,
        fee_percent: float = 0.1,
        position_sizing: PositionSizing | None = None,
        broker_config: BrokerSimulationConfig | None = None,
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
        """BOT-110 — the side every currently open position shares (`_open()`
        rejects mixing Long+Short, see BOT-050 §3), or `None` when flat. Lets
        a caller tell a strategy which side it's in via
        `StrategyContext.current_position_side`, without the strategy ever
        reading `PaperExchange` directly."""
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
            self._mark_to_market(pos, mark_price) for pos in self._positions
        )
        return self._balance + total_open_value

    @staticmethod
    def _mark_to_market(pos: _OpenPosition, mark_price: float) -> float:
        """@brief Current account-value contribution of one open position at
        `mark_price` (BOT-050), gross of any hypothetical exit fee — the
        same convention this always had for LONG (a fee is only ever
        charged on an actual close, never estimated ahead of time).
        @details LONG: `self._balance` already had `capital_deployed` spent
        on it, so the position's current value is simply quantity marked at
        the current price. SHORT: `self._balance` already had
        `capital_deployed` held aside as margin (never actually spent), so
        its current value is that margin plus the unrealized
        (entry - mark) price move — zero change in value exactly when
        `mark_price == entry_price`, same as LONG's zero unrealized PnL at
        that point."""
        if pos.side is PositionSide.LONG:
            return pos.quantity * mark_price
        return pos.balance_before_entry + (pos.entry_price - mark_price) * pos.quantity

    def fill(self, signal: Signal, price: float, time: datetime) -> Trade | None:
        """
        Executes `signal` at `price`/`time`.
        Returns the last closed `Trade` on a SELL/COVER that closed positions, otherwise None.
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
        Realizes every still-open position, either side, at `price`/`time`
        at the end of a backtest run.
        """
        closed = list(
            self._close(PositionSide.LONG, price, time, ExitReason.END_OF_BACKTEST)
        )
        closed += self._close(
            PositionSide.SHORT, price, time, ExitReason.END_OF_BACKTEST
        )
        return closed[-1] if closed else None

    def _slippage_delta(self) -> float:
        return self._broker_config.slippage_ticks * self._broker_config.tick_size

    def _entry_effective_price(self, side: PositionSide, price: float) -> float:
        """A LONG entry buys (pays more with slippage); a SHORT entry sells
        (receives less with slippage) — same direction of unfavorability,
        mirrored."""
        delta = self._slippage_delta()
        if side is PositionSide.LONG:
            return price + delta
        return max(0.0, price - delta)

    def _exit_effective_price(self, side: PositionSide, price: float) -> float:
        """A LONG exit sells (receives less); a SHORT exit/cover buys (pays
        more) — the mirror image of `_entry_effective_price`."""
        delta = self._slippage_delta()
        if side is PositionSide.LONG:
            return max(0.0, price - delta)
        return price + delta

    def _calculate_entry_capital(
        self, side: PositionSide, price: float, current_equity: float
    ) -> tuple[float, float, float]:
        """
        Calculates (capital_deployed, quantity, entry_fee) for opening a
        position, either side, based on position sizing and commission
        model. Returns (0.0, 0.0, 0.0) if sizing or cash is insufficient.
        `capital_deployed` is spent cash for LONG and margin held aside for
        SHORT (BOT-050) — see `_open()`/`_close_one_position()`.
        """
        effective_price = self._entry_effective_price(side, price)
        if effective_price <= 0:
            return 0.0, 0.0, 0.0

        sizing_type = self._position_sizing.type
        sizing_val = self._position_sizing.value

        if sizing_type is PositionSizingType.PERCENT_OF_EQUITY:
            target_capital = current_equity * (sizing_val / 100.0)
        elif sizing_type is PositionSizingType.FIXED_CASH:
            target_capital = sizing_val
        elif sizing_type is PositionSizingType.FIXED_CONTRACTS:
            target_capital = sizing_val * effective_price
        elif sizing_type is PositionSizingType.RISK_PERCENT:
            # risk_amount = current_equity * risk% — the cash lost if the
            # stop is hit. quantity = risk_amount / stop_distance, so
            # capital = quantity * effective_price = risk_amount *
            # (effective_price / stop_distance). stop_distance is a % of
            # effective_price (stop_loss_pct), not the raw entry price, to
            # stay consistent with where slippage is already applied above.
            # Symmetric for both sides — stop_distance is a magnitude, not
            # a signed direction.
            if self._broker_config.stop_loss_pct is None:
                logger.debug(
                    f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: RISK_PERCENT "
                    "sizing requires BrokerSimulationConfig.stop_loss_pct to be set"
                )
                return 0.0, 0.0, 0.0
            stop_distance = effective_price * (
                self._broker_config.stop_loss_pct / 100.0
            )
            risk_amount = current_equity * (sizing_val / 100.0)
            target_capital = risk_amount * (effective_price / stop_distance)
        else:
            target_capital = self._balance

        # Capital deployed cannot exceed currently available liquid cash balance
        target_capital = min(target_capital, self._balance)
        if target_capital <= 0:
            return 0.0, 0.0, 0.0

        comm_type = self._broker_config.commission_type
        comm_val = self._broker_config.commission_value

        if comm_type is CommissionType.PERCENT:
            entry_fee = target_capital * (comm_val / 100.0)
            net_capital = target_capital - entry_fee
            if net_capital <= 0:
                return 0.0, 0.0, 0.0
            quantity = net_capital / effective_price
            capital_deployed = target_capital
        elif comm_type is CommissionType.CASH_PER_ORDER:
            entry_fee = comm_val
            net_capital = target_capital - entry_fee
            if net_capital <= 0:
                return 0.0, 0.0, 0.0
            quantity = net_capital / effective_price
            capital_deployed = target_capital
        elif comm_type is CommissionType.CASH_PER_CONTRACT:
            quantity = target_capital / (effective_price + comm_val)
            if quantity <= 0:
                return 0.0, 0.0, 0.0
            entry_fee = quantity * comm_val
            capital_deployed = target_capital
        else:
            entry_fee = 0.0
            quantity = target_capital / effective_price
            capital_deployed = target_capital

        return capital_deployed, quantity, entry_fee

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

        if self._broker_config.stop_loss_pct is not None:
            stop_pct = self._broker_config.stop_loss_pct / 100.0
            # LONG stop sits BELOW entry (a drop hurts); SHORT stop sits
            # ABOVE entry (a rise hurts) — mirrored.
            stop_loss_price = (
                effective_price * (1 - stop_pct)
                if side is PositionSide.LONG
                else effective_price * (1 + stop_pct)
            )
        else:
            stop_loss_price = None

        if self._broker_config.take_profit_pct is not None:
            tp_pct = self._broker_config.take_profit_pct / 100.0
            # LONG target sits ABOVE entry; SHORT target sits BELOW —
            # mirrored.
            take_profit_price = (
                effective_price * (1 + tp_pct)
                if side is PositionSide.LONG
                else effective_price * (1 - tp_pct)
            )
        else:
            take_profit_price = None

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
        )
        self._positions.append(position)
        slippage_delta = self._slippage_delta()
        slip_sign = "+" if side is PositionSide.LONG else "-"
        logger.info(
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
        """Realizes exactly one open position at `exit_price` (already the
        final fill price — callers apply slippage themselves beforehand if
        the fill type warrants it; a stop-loss/take-profit fill does not,
        see `check_intrabar_stops`). Does not touch `self._positions` —
        callers own removing the position, since `_close()` clears every
        matching-side position at once while `check_intrabar_stops()`
        removes only the subset that triggered this bar.
        `raw_price`/`slippage_delta` are log-only detail for a market-order
        close (`_close()`); left at their defaults for a stop/target fill,
        which has no raw-vs-effective distinction — the target price itself
        is the fill.

        PnL (BOT-050): LONG realizes `net_proceeds - capital_deployed`,
        where `capital_deployed` already embeds the entry fee (it was never
        subtracted out of it, only used to compute a smaller quantity) —
        algebraically this equals `quantity*(exit-entry) - entry_fee -
        exit_fee`. SHORT computes that same expanded form directly (entry
        and exit price roles swapped) since there's no "proceeds" to net
        against for a short — the margin (`capital_deployed`) was reserved,
        not spent, and gets released back plus/minus `pnl`."""
        comm_type = self._broker_config.commission_type
        comm_val = self._broker_config.commission_value

        notional = pos.quantity * exit_price
        if comm_type is CommissionType.PERCENT:
            exit_fee = notional * (comm_val / 100.0)
        elif comm_type is CommissionType.CASH_PER_ORDER:
            exit_fee = comm_val
        elif comm_type is CommissionType.CASH_PER_CONTRACT:
            exit_fee = pos.quantity * comm_val
        else:
            exit_fee = 0.0

        if pos.side is PositionSide.LONG:
            net_proceeds = notional - exit_fee
            self._balance += net_proceeds
            pnl = net_proceeds - pos.balance_before_entry
        else:
            pnl = (
                (pos.entry_price - exit_price) * pos.quantity - pos.entry_fee - exit_fee
            )
            self._balance += pos.balance_before_entry + pnl

        pnl_percent = (
            (pnl / pos.balance_before_entry * 100.0)
            if pos.balance_before_entry > 0
            else 0.0
        )

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
        logger.info(
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
        logger.info(
            f"[paper-exchange] All positions closed "
            f"({len(closed_trades)} trades) | New Balance: {self._balance:,.2f}"
        )
        return closed_trades

    def check_intrabar_stops(
        self, high: float, low: float, time: datetime
    ) -> Sequence[Trade]:
        """
        @brief Checks every open position's stop-loss/take-profit against
        one bar's high/low range and closes whichever triggered (BOT-041,
        extended for SHORT by BOT-050).
        @details Must be called every bar regardless of whether the strategy
        emitted a signal — `fill()` only ever runs when a signal exists, so
        this is the only path that can catch a stop hit on a signal-free
        bar. A position with neither `stop_loss_price` nor
        `take_profit_price` set (the default, `BrokerSimulationConfig`'s
        pct fields are `None`) is never touched here — existing callers
        that never configured SL/TP see zero behavior change. Fills at the
        exact target price, not `high`/`low` themselves, matching real
        stop/limit order semantics (and the Pine Script reference this task
        was modeled on) — no slippage applied, unlike a market-order
        `fill()`. When one bar's range reaches both the stop and the target
        (a real, unresolvable ambiguity — OHLC data cannot say which the
        price touched first), **stop-loss wins**: the conservative
        assumption, documented here because it changes results.

        LONG and SHORT check the opposite edges of the bar for each
        threshold: a LONG stop sits below entry and triggers on `low`, a
        SHORT stop sits above entry and triggers on `high` — mirrored for
        the take-profit target too.
        """
        if not self._positions:
            return []

        triggered: list[tuple[_OpenPosition, float, ExitReason]] = []
        still_open: list[_OpenPosition] = []
        for pos in self._positions:
            if pos.side is PositionSide.LONG:
                stop_hit = (
                    pos.stop_loss_price is not None and low <= pos.stop_loss_price
                )
                target_hit = (
                    pos.take_profit_price is not None and high >= pos.take_profit_price
                )
            else:
                stop_hit = (
                    pos.stop_loss_price is not None and high >= pos.stop_loss_price
                )
                target_hit = (
                    pos.take_profit_price is not None and low <= pos.take_profit_price
                )
            if stop_hit:
                triggered.append((pos, pos.stop_loss_price, ExitReason.STOP_LOSS))
            elif target_hit:
                triggered.append((pos, pos.take_profit_price, ExitReason.TAKE_PROFIT))
            else:
                still_open.append(pos)

        if not triggered:
            return []

        self._positions = still_open
        return [
            self._close_one_position(pos, exit_price, time, reason)
            for pos, exit_price, reason in triggered
        ]
