"""`EPIC-028D` — what a desk shows about its account: how much can be spent,
and what the account is worth.

@details Two value types, one per market, rather than one type whose fields
are `None` wherever a market has no such figure. `AccountSummary` holds the
three figures every desk shows (which venue, the balance an order can spend,
the account's value); each market adds its own.

**Available is not wallet.** On USD-M Futures the wallet balance includes
margin already committed to open positions and orders; `availableBalance` is
what a new order can use. Showing the wallet as spendable (what
`ExchangeConnectionStatus.usdt_balance` has always carried) overstates it by
exactly the margin in use. On Spot, the spendable quote is its `free` part;
`locked` sits in open orders.

**Equity may be unknown.** A Spot account's value needs every holding priced;
when one cannot be, `equity` is `None` rather than a partial sum
(`SpotAccountReader._compute_equity`, `EPIC-027H`). A Futures account's value
is its margin balance (wallet plus unrealized PnL) and is always known.

Plausible extensions, each a new subclass here plus the reader that fills it:
a COIN-M Futures summary (margin in the coin, not USDT); a mainnet venue
(same types, another `venue`); a multi-asset-margin Futures account (the
account-wide `total*` figures instead of the USDT asset's).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
        PositionMode,
    )


@dataclass(frozen=True)
class AccountSummary:
    """The three figures every desk shows, whatever its market."""

    venue: TradingVenue
    #: What a new order can spend, in the quote asset (USDT).
    available_balance: Decimal
    #: What the account is worth in the quote asset; `None` only when it
    #: cannot be computed without guessing.
    equity: Decimal | None


@dataclass(frozen=True)
class FuturesAccountSummary(AccountSummary):
    """A USD-M Futures account, read from its USDT asset."""

    wallet_balance: Decimal
    #: Wallet balance plus unrealized PnL; the same figure as `equity`.
    margin_balance: Decimal
    unrealized_pnl: Decimal
    position_mode: PositionMode


@dataclass(frozen=True)
class SpotAccountSummary(AccountSummary):
    """A Spot account's quote asset, split into spendable and in orders."""

    quote_asset: str
    #: The spendable part; the same figure as `available_balance`.
    quote_free: Decimal
    #: Held by open orders.
    quote_locked: Decimal
