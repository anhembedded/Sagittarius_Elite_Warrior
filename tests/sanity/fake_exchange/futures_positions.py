"""`EPIC-039C` — the fake Futures account's one-way positions and the margin behind them.

@details Split from `futures_account_state.py` along the seam between *what is held*
(this file: the signed amount, the volume-weighted entry, the isolated margin, the figures
that follow from the mark) and *what is owned* (the wallet, the fees, funding and the
reports). A position carries the margin behind it: its notional at the fill over the
leverage, added to on an increase, released in proportion on a decrease, moved by funding
(`add_margin`), and lost whole when the position is liquidated (`close` hands it back). The
liquidation price is computed from it under isolated margin, from the wallet under cross
(`futures_liquidation.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from . import futures_liquidation
from .futures_market import FuturesMarket
from .futures_symbol_config import FuturesSymbolConfig

_ISOLATED = "ISOLATED"


@dataclass
class _Position:
    amount: Decimal
    entry_price: Decimal
    #: The margin behind the position under isolated margin; unused under cross.
    isolated_margin: Decimal = Decimal(0)


class FuturesPositions:
    """Every open position of the account, by symbol."""

    def __init__(
        self, symbol_config: FuturesSymbolConfig, market: FuturesMarket
    ) -> None:
        self._symbol_config = symbol_config
        self._market = market
        self._held: dict[str, _Position] = {}

    def symbols(self) -> list[str]:
        return list(self._held)

    def amount(self, symbol: str) -> Decimal:
        position = self._held.get(symbol)
        return position.amount if position else Decimal(0)

    def entry_price(self, symbol: str) -> Decimal:
        return self._held[symbol].entry_price

    def isolated(self, symbol: str) -> bool:
        return self._symbol_config.margin_type(symbol) == _ISOLATED

    def isolated_margin(self, symbol: str) -> Decimal | None:
        """The margin behind `symbol`'s position under isolated margin; `None` under
        cross or when flat."""
        if symbol not in self._held or not self.isolated(symbol):
            return None
        return self._held[symbol].isolated_margin

    def unrealized(self, symbol: str) -> Decimal:
        position = self._held.get(symbol)
        if position is None:
            return Decimal(0)
        return (
            self._market.mark_price(symbol) - position.entry_price
        ) * position.amount

    def initial_margin(self, symbol: str) -> Decimal:
        position = self._held.get(symbol)
        if position is None:
            return Decimal(0)
        notional = abs(position.amount) * self._market.mark_price(symbol)
        return notional / self._symbol_config.leverage(symbol)

    def total_unrealized(self) -> Decimal:
        return sum((self.unrealized(s) for s in self._held), Decimal(0))

    def total_initial_margin(self) -> Decimal:
        return sum((self.initial_margin(s) for s in self._held), Decimal(0))

    def total_isolated_margin(self) -> Decimal:
        return sum(
            (self._held[s].isolated_margin for s in self._held if self.isolated(s)),
            Decimal(0),
        )

    def liquidation_price(self, symbol: str, wallet: Decimal) -> Decimal | None:
        """Where the position is liquidated: on its isolated margin, or under cross on
        the `wallet`. `None` when flat or when no price does."""
        position = self._held.get(symbol)
        if position is None:
            return None
        margin = position.isolated_margin if self.isolated(symbol) else wallet
        return futures_liquidation.liquidation_price(
            position.amount, position.entry_price, margin
        )

    def add_margin(self, symbol: str, change: Decimal) -> None:
        """Moves the margin behind `symbol`'s position (funding paid is negative)."""
        self._held[symbol].isolated_margin += change

    def close(self, symbol: str) -> Decimal:
        """Removes the position by force; returns the margin that was behind it."""
        return self._held.pop(symbol).isolated_margin

    def move(self, symbol: str, signed: Decimal, price: Decimal) -> Decimal:
        """Applies a signed fill; returns the PnL it realizes."""
        position = self._held.get(symbol)
        leverage = self._symbol_config.leverage(symbol)
        if position is None or position.amount == 0:
            self._held[symbol] = _Position(
                signed, price, abs(signed) * price / leverage
            )
            return Decimal(0)
        if (position.amount > 0) == (signed > 0):
            total = position.amount + signed
            position.entry_price = (
                position.entry_price * position.amount + price * signed
            ) / total
            position.amount = total
            position.isolated_margin += abs(signed) * price / leverage
            return Decimal(0)
        closed = min(abs(signed), abs(position.amount))
        direction = 1 if position.amount > 0 else -1
        realized = (price - position.entry_price) * closed * direction
        remainder = position.amount + signed
        if remainder == 0:
            del self._held[symbol]
        elif (remainder > 0) == (position.amount > 0):
            position.isolated_margin *= abs(remainder) / abs(position.amount)
            position.amount = remainder
        else:
            self._held[symbol] = _Position(
                remainder, price, abs(remainder) * price / leverage
            )
        return realized
