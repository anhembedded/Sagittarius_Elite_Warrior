"""`EPIC-040B` — what a backtest request answers when no result came of it, and the three
answers together."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestOutcome,
)


@dataclass(frozen=True, slots=True)
class BacktestRefusal:
    """Why nothing was replayed, in words the screen shows.

    `missing_candles` says the period's candles are not stored: the screen offers to sync them,
    and never fetches on its own (`BUG-107`). `funding_unavailable` says a Futures period's
    funding history could not be read (`EPIC-039K`): the screen may offer to replay without it,
    in so many words (`FundingRequirement.OPTIONAL`)."""

    reason: str
    missing_candles: bool = False
    funding_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class BacktestCancelled:
    """A replay stopped by its caller: a value, never a partial result."""

    replayed_bars: int
    total_bars: int


type BacktestAnswer = BacktestOutcome | BacktestRefusal | BacktestCancelled
