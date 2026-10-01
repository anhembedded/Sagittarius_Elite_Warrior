"""`EPIC-028I` — what a Futures order panel reads beyond the symbol's
filters: the leverage and its notional cap, the brackets, the mark price,
the book and the position already open.

@details Every figure is the venue's own read (`IOrderEntryTerms`,
`IAccountSnapshot`), never a default: a desk whose reads failed shows "still
loading" rather than sizing against an invented leverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)


@dataclass(frozen=True)
class FuturesEntryContext:
    """One Futures symbol's sizing reads."""

    setting: FuturesSymbolSetting
    brackets: LeverageBrackets
    mark_price: Decimal
    #: `None` when the book could not be read; a market maximum then waits.
    book: BestBidAsk | None
    #: The open position's signed amount (long positive); zero when flat.
    position_amount: Decimal
    #: The wallet balance, the margin behind a cross position's liquidation;
    #: `None` when the account summary could not be read.
    wallet_balance: Decimal | None

    @property
    def notional_headroom(self) -> Decimal:
        """What the leverage still allows on the symbol: its notional cap less
        the position already open, at the mark price."""
        open_notional = abs(self.position_amount) * self.mark_price
        return max(Decimal(0), self.setting.max_notional - open_notional)
