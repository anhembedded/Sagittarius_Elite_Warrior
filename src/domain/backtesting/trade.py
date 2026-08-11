from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Trade:
    """
    @brief A single completed (entry + exit) simulated trade produced by
    `PaperExchange`.
    @details Only ever represents a *closed* trade — an open position isn't a
    Trade yet, precisely so every metric derived from a list of Trades (win
    rate, profit factor, ...) has an unambiguous, fully-realized PnL to work
    from.
    """

    symbol: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    fees_paid: float
