from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason


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
    #: The opening `Signal.reason` (e.g. "EMA Crossover 3/5 crossed above"),
    #: never the closing signal's — defaults to "" so every pre-`BOT-045`
    #: `Trade(...)` call site across the test suite still constructs.
    entry_reason: str = ""
    exit_reason: ExitReason = ExitReason.STRATEGY_SIGNAL
    #: Strategy-specific metrics attached to the *opening* signal (e.g. a
    #: "QML Signal Score") — open-ended by design (`BOT-045`: "tùy vào
    #: chiến thuật"), so the UI must render whatever keys are present rather
    #: than assume a fixed schema.
    metadata: Mapping[str, Any] = field(default_factory=dict)
