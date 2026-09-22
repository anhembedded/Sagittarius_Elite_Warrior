from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


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
    #: BOT-050 — LONG for every trade before this field existed (default),
    #: so no pre-existing `Trade(...)` construction call site needs updating.
    side: PositionSide = PositionSide.LONG
    #: BOT-049 — the leverage this position was opened with (1.0 for every
    #: trade before leverage existed, same reasoning as `side` above). A
    #: `liquidated: bool` was considered and rejected as redundant: whether
    #: this trade was one is always `exit_reason is ExitReason.LIQUIDATION`.
    leverage: float = 1.0
    #: BOT-106B — Maximum Adverse/Favorable Excursion: the worst/best
    #: unrealized `pnl_percent` this position ever reached while open, from
    #: `OpenPosition.mae_percent`/`.mfe_percent`. `0.0` for every trade before
    #: this field existed, same reasoning as `leverage` above.
    mae_percent: float = 0.0
    mfe_percent: float = 0.0
