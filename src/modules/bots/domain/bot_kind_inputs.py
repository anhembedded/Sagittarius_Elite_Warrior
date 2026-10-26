"""`EPIC-029B` — what a bot kind is given to judge the user's parameters.

Four parts, each from a different owner, bundled into one frozen object so a
kind's methods take one argument (`code/quality.md` §7):

  · `config` — the user's parameters, as the definition stores them;
  · `ExchangeTerms` — the venue's filters, the account's fees and trading's
    per-order cap. Live, the executor fills it from trading's
    `IOrderEntryTerms.terms_for()` and `trading.max_notional_per_order_usdt`
    (`EPIC-029E`); the backtest fills it from recorded terms (`EPIC-029D`).
    It is the bots module's own value, so its domain names no other module;
  · `MarketView` — the last price and, when candles are available, the daily
    ATR(14) a range is compared against;
  · `AccountView` — what the account can spend and whether its key may trade
    (`EPIC-034F`), once the Connect step has read it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.contracts.wire_name import wire_name
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_LIMITS,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)


@dataclass(frozen=True, slots=True)
class PriceBand:
    """`BUG-147` — how far from the market an order's price may be, as
    multiples of the reference price: Binance Spot's `PERCENT_PRICE_BY_SIDE`.

    @details Binance holds a BUY to `[buy_down, buy_up] × average price` and a
    SELL to `[sell_down, sell_up] × average price`, the average taken over the
    filter's `avgPriceMins`. A check here uses the last price as the
    reference: close to the average in a normal market, and the only price a
    plan is drawn at.
    """

    buy_down: Decimal
    buy_up: Decimal
    sell_down: Decimal
    sell_up: Decimal

    def __post_init__(self) -> None:
        if not (
            0 < self.buy_down <= self.buy_up and 0 < self.sell_down <= self.sell_up
        ):
            raise ValueError("a price band's multipliers must be positive, down <= up")


#: The one status in which a symbol accepts new orders (Binance Spot's
#: `TRADING`); every other status, `BREAK`, `HALT` and `CANCEL_ONLY` among them,
#: still lets an order be cancelled.
TRADING_STATUS = "TRADING"


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
    #: The most orders the bot may hold open: trading's per-owner cap (ADR
    #: O1). The venue's `MAX_NUM_ORDERS` filter is not read; Binance Spot's
    #: is 200, and the configured cap stays below it.
    max_open_orders: int
    #: `MARKET_LOT_SIZE`'s step, which Binance holds a MARKET order to; `None`
    #: when the venue publishes none, and `LOT_SIZE`'s step applies.
    market_step_size: Decimal | None = None
    #: The venue's price band (`BUG-147`); `None` when it publishes none, and
    #: the band check says it did not run.
    price_band: PriceBand | None = None
    #: The venue's status for the symbol, as it says it (`EPIC-035E`): only
    #: `TRADING_STATUS` accepts new orders.
    symbol_status: str = TRADING_STATUS

    @property
    def trades(self) -> bool:
        """Whether the exchange accepts new orders on the symbol."""
        return self.symbol_status == TRADING_STATUS

    @property
    def market_step(self) -> Decimal:
        """The step a market order's base quantity is rounded down to."""
        return self.market_step_size or self.step_size

    def __post_init__(self) -> None:
        if self.tick_size <= 0 or self.step_size <= 0:
            raise ValueError("tick_size and step_size must be positive")
        if self.max_open_orders < 1:
            raise ValueError("max_open_orders must be at least 1")


#: How often a Futures venue settles funding: the 8 hours Binance's USD-M perpetuals
#: use by default (`EPIC-039G`). A symbol's schedule can differ; the next settlement time
#: the exchange reports is the exact one.
FUNDING_INTERVAL = timedelta(hours=8)


@dataclass(frozen=True, slots=True)
class FundingView:
    """`EPIC-039G` — the funding rate a venue charges now, as the bots module's own value."""

    #: A fraction of the position's notional per `FUNDING_INTERVAL`; positive means longs
    #: pay shorts. `None` when the rate could not be read: unknown, never zero.
    rate: Decimal | None


@dataclass(frozen=True, slots=True)
class MarketView:
    """What the market looks like when the parameters are judged."""

    last_price: Decimal
    #: ATR(14) on the daily timeframe; `None` when no candles are available,
    #: in which case the range-versus-ATR check reports that it did not run.
    daily_atr: Decimal | None = None
    #: Orders already open on the symbol that the plan did not place (`EPIC-035V`,
    #: L7); `None` when they were not read, and the check then says it did not run.
    foreign_open_orders: int | None = None
    #: `EPIC-039G` — the funding the venue charges; `None` on a venue with none (Spot),
    #: a `FundingView` whose rate is `None` where the venue charges it and it could not
    #: be read. The two are different facts, so neither is a zero.
    funding: FundingView | None = None
    #: The symbol's two assets, so a sentence can say `ETH` and `USDT` where a number is
    #: money or a quantity (`BUG-210`). `""` when they are not known; a sentence then
    #: falls back to "the asset" and "quote" rather than guess a name.
    base_asset: str = ""
    quote_asset: str = ""
    #: Why there is no `daily_atr`, when the reader could say (`BOT-227`).
    daily_atr_unavailable: str = ""

    def __post_init__(self) -> None:
        if self.last_price <= 0:
            raise ValueError("last_price must be positive")


@dataclass(frozen=True, slots=True)
class AccountView:
    """`EPIC-034F` — what the venue's account says about money and permission,
    as the bots module's own value (the Connect step's snapshot, narrowed to
    what a kind's constraints read).

    @details `can_trade` is the account's own flag: `None` means the exchange
    did not say, which is not the same as "may trade".
    """

    #: What a new order can spend, in `quote_asset`.
    available_quote: Decimal
    quote_asset: str
    can_trade: bool | None
    #: The venue's title, for a sentence that names where the money is.
    venue_title: str

    def __post_init__(self) -> None:
        if self.available_quote < 0:
            raise ValueError("available_quote must not be negative")


@dataclass(frozen=True, slots=True)
class MarginView:
    """`EPIC-039E` — `AccountView`'s Futures counterpart: what the venue's account lets a
    new order reserve as **margin**, as the Connect step reads it. A Spot venue keeps
    `AccountView.available_quote` and its words unchanged; a Futures venue is shown this.
    """

    #: What a new order can reserve as margin, in `quote_asset`.
    available_margin: Decimal
    quote_asset: str
    can_trade: bool | None
    #: The venue's title, for a sentence that names where the money is.
    venue_title: str

    def __post_init__(self) -> None:
        if self.available_margin < 0:
            raise ValueError("available_margin must not be negative")


@wire_name("sew.plan-risk-facts/1")
@dataclass(frozen=True, slots=True)
class PlanRiskFacts:
    """`EPIC-039J` — what a position venue says about the symbol that a plan's liquidation is
    estimated from: the account's setting for it and the leverage brackets. A venue with no
    such risk (Spot) supplies none, and no risk verdict is asked for."""

    setting: FuturesSymbolSetting
    brackets: LeverageBrackets


@dataclass(frozen=True, slots=True)
class BotKindInputs:
    """One kind's whole input: the user's parameters and the world they meet."""

    config: Mapping[str, str]
    terms: ExchangeTerms
    market: MarketView
    #: The Connect step's read of the account; `None` until it was read, and
    #: the constraints that need it then say they did not run.
    account: AccountView | None = None
    #: The directions and leverage the bot's venue allows (the venue profile's, `EPIC-039B`).
    #: Without the venue's word it is the Spot profile's: long, at 1.
    limits: ExposureLimits = SPOT_LIMITS
    #: The symbol's risk facts on a position venue (`EPIC-039J`); `None` until they are read,
    #: and on Spot, where the plan has no liquidation to judge.
    risk: PlanRiskFacts | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", MappingProxyType(dict(self.config)))
