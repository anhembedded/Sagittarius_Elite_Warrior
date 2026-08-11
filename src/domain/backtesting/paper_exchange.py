from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


@dataclass
class _OpenPosition:
    quantity: float
    entry_price: float
    entry_time: datetime
    balance_before_entry: float
    entry_fee: float


class PaperExchange:
    """
    @brief Simulated single-symbol, long-only exchange for the static
    backtest engine (BOT-021).

    @details All-in position sizing — a BUY deploys the entire current
    balance — and no pyramiding: a BUY while already in a position, or a
    SELL with no open position, is a no-op. This matches the long-only,
    single-position contract `EmaCrossoverStrategy` already documents itself
    against ("whether a Sell with no open position does anything is a
    PaperExchange concern"). A taker-style fee (percent of notional) is
    charged on both entry and exit.

    Callers are responsible for filling at the NEXT bar's open relative to
    the bar that produced the signal, never the signal's own triggering bar
    — `PaperExchange` itself is agnostic to *when* a fill happens, it just
    executes at whatever price/time it's given.
    """

    def __init__(
        self, symbol: str, initial_balance: float, fee_percent: float = 0.1
    ) -> None:
        if initial_balance <= 0:
            raise ValueError(f"initial_balance must be positive, got {initial_balance}")
        if fee_percent < 0:
            raise ValueError(f"fee_percent must be >= 0, got {fee_percent}")
        self._symbol = symbol
        self._balance = initial_balance
        self._fee_percent = fee_percent
        self._position: _OpenPosition | None = None
        self._trades: list[Trade] = []

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def is_in_position(self) -> bool:
        return self._position is not None

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)

    def equity(self, mark_price: float) -> float:
        """Cash balance if flat, or the open position marked to `mark_price`."""
        if self._position is None:
            return self._balance
        return self._position.quantity * mark_price

    def fill(self, signal: Signal, price: float, time: datetime) -> Trade | None:
        """Executes `signal` at `price`/`time`. Returns the closed `Trade` on
        a SELL that actually closed a position, otherwise None (BUY opens
        but never itself completes a Trade; a no-op fill also returns None)."""
        if signal.action is SignalAction.BUY:
            self._open(price, time)
            return None
        if signal.action is SignalAction.SELL:
            return self._close(price, time)
        return None

    def force_close(self, price: float, time: datetime) -> Trade | None:
        """Realizes any still-open position at `price`/`time` — used at the
        end of a backtest run so every trade counted toward the metrics is a
        genuinely closed trade, never one with an unresolved open PnL."""
        return self._close(price, time)

    def _open(self, price: float, time: datetime) -> None:
        if self._position is not None:
            return  # already in a position — no pyramiding
        entry_fee = self._balance * self._fee_percent / 100
        capital = self._balance - entry_fee
        quantity = capital / price
        self._position = _OpenPosition(
            quantity=quantity,
            entry_price=price,
            entry_time=time,
            balance_before_entry=self._balance,
            entry_fee=entry_fee,
        )
        self._balance = 0.0

    def _close(self, price: float, time: datetime) -> Trade | None:
        if self._position is None:
            return None
        position = self._position
        proceeds = position.quantity * price
        exit_fee = proceeds * self._fee_percent / 100
        self._balance = proceeds - exit_fee
        pnl = self._balance - position.balance_before_entry
        pnl_percent = (
            (pnl / position.balance_before_entry) * 100
            if position.balance_before_entry
            else 0.0
        )
        trade = Trade(
            symbol=self._symbol,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=time,
            exit_price=price,
            quantity=position.quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            fees_paid=position.entry_fee + exit_fee,
        )
        self._trades.append(trade)
        self._position = None
        return trade
