"""`EPIC-047H` — port: read the exchange again for one bot, for the VPS tab (decision record 2026-10-27, D4).

@details The host's refresher (`operations`) decides *when* and *how much weight* a read may spend;
this port is *what* is read: the bot's exchange facts, its planner inputs, its fills (each its own scope,
so each is paced and charged on its own) and a venue's static exchange info. Every read goes out at `RequestPriority.ROUTINE`, so it
waits at the 70 % line and never touches the exit reserve; it places, cancels and starts nothing.

A read that fails leaves the last good one in place: `refresh` reports it in `RefreshOutcome.problem`
and records nothing, and the refresher keeps the last snapshot and its `read_at`.

@par Extension cases
  · another scope (the funding history) - one member of `RefreshScope` and one read in the adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class RefreshScope(Enum):
    """One read per scope, so the host's weight ceiling can pace each of them: a scope is never a bundle."""

    #: The bot's exchange facts: account, position, resting orders, settings, brackets.
    FACTS = "facts"
    #: The planner's inputs: filters, fees, mid price, daily ATR and Bollinger range.
    PLANNER = "planner"
    #: The bot's fills, from the venue's order history.
    FILLS = "fills"
    #: The candle store of the bot's symbol, brought up to now for each timeframe the chart pins (a backfill, then an
    #: incremental sync). Fetched by `market_data`'s own client, which the venue's weight gate does not see.
    CANDLES = "candles"


@dataclass(frozen=True, slots=True)
class RefreshTarget:
    """A stored bot on an enabled venue."""

    bot_id: str
    venue: TradingVenue
    symbol: str
    #: Whether the bot is not at rest (anything but DRAFT and STOPPED): it may hold a position or resting
    #: orders, so the scheduled refresh keeps its facts current. A bot at rest is read on demand only.
    exposure: bool


@dataclass(frozen=True, slots=True)
class RefreshOutcome:
    #: When the read was taken; `None` when it failed.
    read_at: datetime | None
    #: Why it failed, in words that name the part and never the exchange's own text; empty when it was read.
    problem: str = ""

    def __post_init__(self) -> None:
        if (self.read_at is None) == (not self.problem):
            raise ValueError("a read either happened (read_at) or failed (problem)")


class IBotReadRefresh(ABC):
    @abstractmethod
    def targets(self) -> tuple[RefreshTarget, ...]:
        """Every stored bot on an enabled venue, in bot-id order. Reads the bot store; asks the exchange nothing."""

    @abstractmethod
    def refresh(self, bot_id: str, scope: RefreshScope) -> RefreshOutcome:
        """Read `scope` for the bot, at ROUTINE priority. Never raises."""

    @abstractmethod
    def refresh_static(self, venue: TradingVenue) -> RefreshOutcome:
        """Read the venue's exchange info again and keep the filters of its bots' symbols. Never raises."""
