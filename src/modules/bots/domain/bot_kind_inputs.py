"""`EPIC-029B` — what a bot kind is given to judge the user's parameters.

Three parts, each from a different owner, bundled into one frozen object so a
kind's methods take one argument (`code/quality.md` §7):

  · `config` — the user's parameters, as the definition stores them;
  · `ExchangeTerms` — the venue's filters, the account's fees and trading's
    per-order cap. Live, the executor fills it from trading's
    `IOrderEntryTerms.terms_for()` and `trading.max_notional_per_order_usdt`
    (`EPIC-029E`); the backtest fills it from recorded terms (`EPIC-029D`).
    It is the bots module's own value, so its domain names no other module;
  · `MarketView` — the last price and, when candles are available, the daily
    ATR(14) a range is compared against.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ExchangeTerms:
    """The numbers the exchange and trading will hold an order to."""

    tick_size: Decimal
    step_size: Decimal
    min_notional: Decimal
    maker_fee: Decimal
    taker_fee: Decimal
    #: Trading's per-order cap (ADR D21, O5): configurable, read at runtime.
    max_notional_per_order: Decimal

    def __post_init__(self) -> None:
        if self.tick_size <= 0 or self.step_size <= 0:
            raise ValueError("tick_size and step_size must be positive")


@dataclass(frozen=True, slots=True)
class MarketView:
    """What the market looks like when the parameters are judged."""

    last_price: Decimal
    #: ATR(14) on the daily timeframe; `None` when no candles are available,
    #: in which case the range-versus-ATR check reports that it did not run.
    daily_atr: Decimal | None = None

    def __post_init__(self) -> None:
        if self.last_price <= 0:
            raise ValueError("last_price must be positive")


@dataclass(frozen=True, slots=True)
class BotKindInputs:
    """One kind's whole input: the user's parameters and the world they meet."""

    config: Mapping[str, str]
    terms: ExchangeTerms
    market: MarketView

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))
