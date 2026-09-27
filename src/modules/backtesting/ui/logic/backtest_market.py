"""`EPIC-027D` — the markets the Backtest screen offers, in one place.

The selector's options, their labels, and how a persisted or typed value
becomes a `MarketType` all live here, so the combo, the run-config builder,
the result text and the state validator cannot disagree about which markets
exist or what they are called.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    SIMULATED_MARKETS,
)

#: Selector order: the default first. Every entry must be one the engine can
#: simulate (`SIMULATED_MARKETS`); COIN-M is not offered (ADR D1).
BACKTEST_MARKETS: tuple[MarketType, ...] = (
    MarketType.FUTURES_USD_M,
    MarketType.SPOT,
)

_LABELS: dict[MarketType, str] = {
    MarketType.FUTURES_USD_M: "Futures (USDⓈ-M)",
    MarketType.SPOT: "Spot",
}

#: What an unknown or unsupported stored value falls back to: the screen's
#: own default (`BrokerSimViewModel.DEFAULT_MARKET`), never a guess.
_FALLBACK_MARKET = MarketType.FUTURES_USD_M


def market_label(market: MarketType) -> str:
    return _LABELS[market]


def market_from_value(value: str) -> MarketType:
    """@brief The market a ViewModel value names.
    @details A value from a hand-edited or older state file that names no
    simulated market falls back to the default rather than raising — a
    screen that refuses to open is worse than one that opens on the default
    (the same rule `run_config_builder._position_sizing` applies)."""
    try:
        market = MarketType(value)
    except ValueError:
        return _FALLBACK_MARKET
    return market if market in SIMULATED_MARKETS else _FALLBACK_MARKET
