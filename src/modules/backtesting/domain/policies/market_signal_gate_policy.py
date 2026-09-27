from __future__ import annotations

import logging
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)

logger = logging.getLogger("App.PaperExchange")

#: The signal actions each market cannot execute. A market absent here
#: executes every action. Spot is long-only (ADR
#: `DECISION_2026-09-26_spot_market_axis.md` D3, D4): it has no short side to
#: open or cover.
_REFUSED_ACTIONS: dict[MarketType, frozenset[SignalAction]] = {
    MarketType.SPOT: frozenset({SignalAction.SHORT, SignalAction.COVER}),
}


class MarketSignalGatePolicy:
    """
    @brief Domain policy deciding which strategy signals the simulated market
    can execute, and counting the ones it refuses (`EPIC-027B`).
    @details `PaperExchange.fill()` asks this before a signal becomes a
    position, so strategies stay market-agnostic and the exchange refuses what
    the market cannot do, the way a real Spot exchange would. A refused signal
    is dropped, never remapped (ADR D4: a SHORT is not a SELL). The refusal
    count is a result fact — `BacktestResult.ignored_short_signals`.

    Extension cases, each a local change: a market restricting another action
    (one `_REFUSED_ACTIONS` entry); a per-symbol restriction such as a
    margin-disabled pair (a second input to `admits()`); counting refusals per
    action for the report (`EPIC-027E`, a dict instead of an int).
    """

    def __init__(self, market_type: MarketType) -> None:
        self._market_type = market_type
        self._refused_actions = _REFUSED_ACTIONS.get(market_type, frozenset())
        self._refused_count = 0

    @property
    def refused_count(self) -> int:
        return self._refused_count

    def admits(self, action: SignalAction) -> bool:
        return action not in self._refused_actions

    def record_refusal(self, action: SignalAction, time: datetime) -> None:
        """@brief Counts one refused signal and logs it at DEBUG (never INFO:
        this runs per signal inside the backtest loop, `BUG-042`)."""
        self._refused_count += 1
        logger.debug(
            f"[spot-gate] {action.value} ignored at {time.isoformat()}: "
            f"{self._market_type.value} cannot execute it"
        )

    def log_run_summary(self) -> None:
        """@brief One INFO line per simulation pass (a static run makes up to three:
        full range plus the two BOT-080 out-of-sample halves) for a market
        that refuses anything."""
        if self._refused_actions:
            logger.info(
                f"[spot-gate] {self._refused_count} short-side signal(s) "
                f"ignored in this simulation: {self._market_type.value} is long-only"
            )
