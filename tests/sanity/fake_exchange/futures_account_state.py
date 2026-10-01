"""`EPIC-028O` — the fake USD-M Futures account: its USDT wallet, one-way
positions and Multi-Assets mode, moved by market fills.

@details A market order fills at once at the book (`futures_market`): a buy
at the ask, a sell at the bid. A fill:
- charges the taker fee (0.05 %, `commissionRate`'s answer) on its notional
  from the wallet;
- opens or adds to a position at the volume-weighted entry price, or reduces
  it and books the realized PnL `(fill − entry) × closed quantity` (the sign
  flipped for a short) into the wallet; a fill past zero opens the rest the
  other way at the fill price.

Figures follow Binance's single-asset rules: margin balance is wallet plus
unrealized PnL at the mark, a position's initial margin is its notional at
the mark over its leverage, and available is margin balance less initial
margin. In Multi-Assets mode Binance reports the account-wide `total*`
figures and `availableBalance` in USD across every asset; this account holds
USDT only, so they equal the USDT figures, and the mode changes only what the
app must read. There is no liquidation, no funding and no maintenance check.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from . import futures_market
from .futures_symbol_config import FuturesSymbolConfig

_TAKER_FEE_RATE = Decimal("0.0005")
_STARTING_WALLET = Decimal(15000)
_SIDE_BUY = "BUY"


@dataclass
class _Position:
    amount: Decimal
    entry_price: Decimal


@dataclass(frozen=True)
class FuturesFill:
    """One market fill, as the order and trade rows report it."""

    price: Decimal
    quantity: Decimal
    commission: Decimal
    realized_pnl: Decimal


class FuturesAccountState:
    """One instance per fake server."""

    def __init__(self, symbol_config: FuturesSymbolConfig) -> None:
        #: The leverage each position's initial margin is computed at.
        self._symbol_config = symbol_config
        self._wallet = _STARTING_WALLET
        self._positions: dict[str, _Position] = {}
        self.multi_assets = False

    def fill_market(self, symbol: str, side: str, quantity: Decimal) -> FuturesFill:
        """@brief Fills a market order at the book and moves the account."""
        bid, ask = futures_market.best_bid_ask(symbol)
        return self.fill_at(symbol, side, quantity, ask if side == _SIDE_BUY else bid)

    def fill_at(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal
    ) -> FuturesFill:
        """@brief Fills at `price`: the account rule `fill_market` applies,
        open to a test that needs fills at different prices."""
        signed = quantity if side == _SIDE_BUY else -quantity
        commission = quantity * price * _TAKER_FEE_RATE
        realized = self._move_position(symbol, signed, price)
        self._wallet += realized - commission
        return FuturesFill(price, quantity, commission, realized)

    def position_amount(self, symbol: str) -> Decimal:
        position = self._positions.get(symbol)
        return position.amount if position else Decimal(0)

    def account(self) -> dict[str, Any]:
        """`GET /fapi/v2/account`."""
        unrealized = sum(
            (self._unrealized(symbol) for symbol in self._positions), Decimal(0)
        )
        initial = sum(
            (self._initial_margin(symbol) for symbol in self._positions), Decimal(0)
        )
        margin = self._wallet + unrealized
        available = margin - initial
        return {
            "totalWalletBalance": _q(self._wallet),
            "totalUnrealizedProfit": _q(unrealized),
            "totalMarginBalance": _q(margin),
            "totalInitialMargin": _q(initial),
            "availableBalance": _q(available),
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": _q(self._wallet),
                    "unrealizedProfit": _q(unrealized),
                    "marginBalance": _q(margin),
                    "initialMargin": _q(initial),
                    "availableBalance": _q(available),
                }
            ],
            "positions": [
                {
                    "symbol": symbol,
                    "positionAmt": _q(position.amount),
                    "entryPrice": _q(position.entry_price),
                    "unrealizedProfit": _q(self._unrealized(symbol)),
                    "isolated": False,
                    "positionSide": "BOTH",
                }
                for symbol, position in self._positions.items()
            ],
        }

    def position_risk(self, symbol: str | None) -> list[dict[str, Any]]:
        """`GET /fapi/v3/positionRisk`: one row per open position, the v3
        shape (no `leverage` or `marginType` field, `BUG-114`); `notional`
        is signed, negative for a short, as Binance sends it."""
        rows = []
        for held, position in self._positions.items():
            if symbol is not None and held != symbol:
                continue
            mark = futures_market.mark_price(held)
            notional = position.amount * mark
            rows.append(
                {
                    "symbol": held,
                    "positionSide": "BOTH",
                    "positionAmt": _q(position.amount),
                    "entryPrice": _q(position.entry_price),
                    "breakEvenPrice": _q(position.entry_price),
                    "markPrice": _q(mark),
                    "unRealizedProfit": _q(self._unrealized(held)),
                    "liquidationPrice": "0",
                    "isolatedMargin": "0",
                    "notional": _q(notional),
                    "marginAsset": "USDT",
                    "isolatedWallet": "0",
                    "initialMargin": _q(self._initial_margin(held)),
                    "maintMargin": "0",
                    "positionInitialMargin": _q(self._initial_margin(held)),
                    "openOrderInitialMargin": "0",
                    "adl": 1,
                    "bidNotional": "0",
                    "askNotional": "0",
                    "updateTime": 0,
                }
            )
        return rows

    def _move_position(self, symbol: str, signed: Decimal, price: Decimal) -> Decimal:
        """Applies a signed fill; returns the PnL it realizes."""
        position = self._positions.get(symbol)
        if position is None or position.amount == 0:
            self._positions[symbol] = _Position(signed, price)
            return Decimal(0)
        if (position.amount > 0) == (signed > 0):
            total = position.amount + signed
            position.entry_price = (
                position.entry_price * position.amount + price * signed
            ) / total
            position.amount = total
            return Decimal(0)
        closed = min(abs(signed), abs(position.amount))
        direction = 1 if position.amount > 0 else -1
        realized = (price - position.entry_price) * closed * direction
        remainder = position.amount + signed
        if remainder == 0:
            del self._positions[symbol]
        elif (remainder > 0) == (position.amount > 0):
            position.amount = remainder
        else:
            self._positions[symbol] = _Position(remainder, price)
        return realized

    def _unrealized(self, symbol: str) -> Decimal:
        position = self._positions[symbol]
        mark = futures_market.mark_price(symbol)
        return (mark - position.entry_price) * position.amount

    def _initial_margin(self, symbol: str) -> Decimal:
        position = self._positions[symbol]
        notional = abs(position.amount) * futures_market.mark_price(symbol)
        return notional / self._symbol_config.leverage(symbol)


def _q(value: Decimal) -> str:
    """Eight decimals, as Binance formats its account figures."""
    return f"{value:.8f}"
