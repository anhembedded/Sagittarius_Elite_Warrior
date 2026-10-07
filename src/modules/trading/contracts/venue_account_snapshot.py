"""`EPIC-034D` — everything the Connect step learns about one account and one
symbol, read together and kept as one value.

@details A bot is designed against these numbers: what the account can spend,
what the venue charges, whether the account may trade, the symbol's filters
and the price. They are read at one moment (`read_at`), so no figure is newer
than another by more than one read, and the value is immutable: a later read
makes a new snapshot, never a changed one (`domain-truth-rule.md`).

`can_trade` is the account's own flag. `None` means the exchange's answer
carried none, which is not the same as "may trade".

Plausible extensions, each a new field with a default: the open-order count
against the venue's limit (the count itself is `EPIC-034E`'s).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

#: Phase 1 trades USDT-quoted pairs only (`EPIC-027H` ADR D9): the asset every
#: snapshot's spendable balance is in.
QUOTE_ASSET = "USDT"


@dataclass(frozen=True)
class VenueAccountSnapshot:
    source: AccountSource
    symbol: str
    read_at: datetime
    quote_asset: str
    #: What a new order can spend, in `quote_asset`.
    available: Decimal
    #: The Spot balances that are not dust; empty on Futures, which holds
    #: margin, not assets.
    holdings: tuple[SpotHolding, ...]
    commission: CommissionRate
    can_trade: bool | None
    rules: SymbolOrderMetadata
    #: The symbol's price on the book when it was read.
    price: Decimal

    def free_of(self, asset: str) -> Decimal:
        """What the account holds free of `asset`; zero when it holds none."""
        return next((h.free for h in self.holdings if h.asset == asset), Decimal(0))
