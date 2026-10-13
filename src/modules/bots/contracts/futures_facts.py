"""`EPIC-039E` — what a Futures venue says about a bot's symbol and account, as one value.

@details The Futures twin of `ExchangeFacts` (`exchange_facts.py`), with the same three
states: asked and not answered yet (`ExchangeChecking`), asked and not answered at all
(`ExchangeUnavailable`, with the reason), and `FuturesLoaded`, the facts read at one moment
and immutable. An unreadable fact is never zero: the reader answers `ExchangeUnavailable` for
it. A Futures rule (`futures_rules.py`) reads a fact only from the loaded state.

@par What is not here yet
`position` is the exchange's signed position on the symbol. Whether some of it is the bot's
own, and the `earlier_runs` analogue, need the exposure book (`EPIC-039D`); until then a
start treats every position as foreign, which is right because a start owns none.

@par Extension cases
  · Cross margin - a second `MarginType` already reads through `symbol_setting`; a rule is
    added to `FUTURES_RULES`;
  · Multi-Assets mode - a new field with a default and one rule;
  · a foreign/own split of the position - `039D` adds a field and the rule reads it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeSnapshot,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)


@dataclass(frozen=True, slots=True)
class FuturesFacts:
    """The facts a Futures readiness rule may use, read together."""

    venue_title: str
    symbol: str
    quote_asset: str
    read_at: datetime
    #: What a new order can spend as margin, in `quote_asset`.
    available_margin: Decimal
    #: The exchange's signed position on the symbol: positive long, negative short, zero flat.
    position: Decimal
    position_mode: PositionMode
    symbol_setting: FuturesSymbolSetting
    brackets: LeverageBrackets
    own_open_orders: int
    #: Open orders on the symbol that no bot placed.
    foreign_open_orders: int
    #: The account's own flag; `None` when the exchange did not say.
    can_trade: bool | None

    def __post_init__(self) -> None:
        if self.available_margin < 0:
            raise ValueError("an exchange fact is never a negative amount")
        if self.own_open_orders < 0 or self.foreign_open_orders < 0:
            raise ValueError("an order count is never negative")
        if self.read_at.tzinfo is None:
            raise ValueError("an exchange snapshot needs a timezone-aware instant")

    def bracket_for(self, notional: Decimal) -> LeverageBracket:
        """The leverage bracket `notional` falls in."""
        return self.brackets.bracket_for(notional)


@dataclass(frozen=True, slots=True)
class FuturesLoaded:
    facts: FuturesFacts


type FuturesSnapshot = ExchangeChecking | ExchangeUnavailable | FuturesLoaded
#: What `IVenueFacts` answers: Spot's snapshot unchanged, or Futures'.
type VenueSnapshot = ExchangeSnapshot | FuturesSnapshot
