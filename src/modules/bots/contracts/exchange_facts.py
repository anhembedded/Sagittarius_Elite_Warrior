"""`BOT-174` — what the exchange says about a bot's symbol and account, as one value.

@details Readiness used to be judged from state this process holds, so a check
that needs the venue's facts (the free base, the orders resting on the symbol,
what earlier runs left) had nowhere to stand. An `ExchangeSnapshot` is that
place: read off the UI thread when a bot is selected, again on demand and
whenever the bot's state changes, then handed to pure rules
(`exchange_rules.py`) beside the local state.

It has exactly three states, and a rule can read a fact only from the third:

  · `ExchangeChecking`: asked, not answered yet. Nothing is known, so the bot is
    not claimed to be ready;
  · `ExchangeUnavailable`: asked and not answered, with the reason in words. It
    is never an empty account or a zero balance;
  · `ExchangeLoaded`: the facts, read at one moment (`read_at`) and immutable
    (`domain-truth-rule.md`): a later read makes a new snapshot.

Plausible extensions, each a new field with a default plus one rule in
`exchange_rules.RULES`: the key's permission set beyond `can_trade`; the venue's
open-order limit against the ladder's order count; the BNB balance a fee needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class ExchangeFacts:
    """The facts a readiness rule may use, read together."""

    #: The venue's title, for a sentence that names where the money is.
    venue_title: str
    symbol: str
    base_asset: str
    quote_asset: str
    read_at: datetime
    base_free: Decimal
    base_locked: Decimal
    quote_free: Decimal
    quote_locked: Decimal
    #: The base reserved by this bot's own resting SELLs. A Resume cancels
    #: them before it lays the ladder, so it frees what they lock.
    own_sell_base: Decimal
    #: The quote reserved by this bot's own resting BUYs (freed the same way).
    own_buy_quote: Decimal
    own_open_orders: int
    #: Open orders on the symbol that no bot placed.
    foreign_open_orders: int
    #: What the bot's earlier runs left, or why that is not known.
    earlier_runs: EarlierRunsInventory
    #: The account's own flag; `None` when the exchange did not say.
    can_trade: bool | None

    def __post_init__(self) -> None:
        amounts = (
            self.base_free,
            self.base_locked,
            self.quote_free,
            self.quote_locked,
            self.own_sell_base,
            self.own_buy_quote,
        )
        if any(amount < _ZERO for amount in amounts):
            raise ValueError("an exchange fact is never a negative amount")
        if self.own_open_orders < 0 or self.foreign_open_orders < 0:
            raise ValueError("an order count is never negative")
        if self.read_at.tzinfo is None:
            raise ValueError("an exchange snapshot needs a timezone-aware instant")


@dataclass(frozen=True, slots=True)
class ExchangeChecking:
    """Asked, not answered yet."""


@dataclass(frozen=True, slots=True)
class ExchangeUnavailable:
    """Asked, and the exchange (or the way to it) did not answer."""

    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("an unavailable snapshot names why")


@dataclass(frozen=True, slots=True)
class ExchangeLoaded:
    facts: ExchangeFacts


type ExchangeSnapshot = ExchangeChecking | ExchangeUnavailable | ExchangeLoaded
