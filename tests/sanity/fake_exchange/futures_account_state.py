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
figures and `availableBalance` in USD across every margin asset: the account
then also holds a fixed BNB margin balance worth `_BNB_MARGIN_USD`, in its own
asset row and in the totals, so a reader that took the USDT row instead of the
totals is told apart (PR #304 review, finding 4).

`EPIC-039C` — a resting order that fills pays the maker fee (0.02 %, what
`commissionRate` answers), a market fill the taker fee. A position carries the
isolated margin behind it (its notional at the fill over the leverage, added to on an
increase and released in proportion on a decrease), which `positionRisk` reports and the
liquidation price is computed from (`futures_liquidation.py`). `apply_funding` charges a
settlement and `liquidate` closes a position by force, losing its whole isolated margin.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from . import futures_liquidation
from .futures_funding import FuturesFunding
from .futures_market import FuturesMarket
from .futures_symbol_config import FuturesSymbolConfig

TAKER_FEE_RATE = Decimal("0.0005")
MAKER_FEE_RATE = Decimal("0.0002")
_STARTING_WALLET = Decimal(15000)
#: The BNB margin a Multi-Assets account also counts, in USD.
_BNB_MARGIN_USD = Decimal(600)
_SIDE_BUY = "BUY"
_ISOLATED = "ISOLATED"


@dataclass
class _Position:
    amount: Decimal
    entry_price: Decimal
    #: The margin behind the position under isolated margin; unused under cross.
    isolated_margin: Decimal = Decimal(0)


@dataclass(frozen=True)
class FuturesFill:
    """One market fill, as the order and trade rows report it."""

    price: Decimal
    quantity: Decimal
    commission: Decimal
    realized_pnl: Decimal

    def as_trade_row(
        self, order: dict[str, Any], trade_id: int, maker: bool, at_ms: int
    ) -> dict[str, Any]:
        """The row `GET /fapi/v1/userTrades` reports for this fill of `order`."""
        return {
            "symbol": order["symbol"],
            "id": trade_id,
            "orderId": order["orderId"],
            "side": order["side"],
            "price": str(self.price),
            "qty": str(self.quantity),
            "realizedPnl": f"{self.realized_pnl:.8f}",
            "quoteQty": str(self.price * self.quantity),
            "commission": f"{self.commission:.8f}",
            "commissionAsset": "USDT",
            "time": at_ms,
            "positionSide": "BOTH",
            "buyer": order["side"] == "BUY",
            "maker": maker,
        }


class FuturesAccountState:
    """One instance per fake server."""

    def __init__(
        self, symbol_config: FuturesSymbolConfig, market: FuturesMarket | None = None
    ) -> None:
        #: The leverage each position's initial margin is computed at.
        self._symbol_config = symbol_config
        self._market = market or FuturesMarket(FuturesFunding())
        self._wallet = _STARTING_WALLET
        self._positions: dict[str, _Position] = {}
        self.multi_assets = False

    def fill_market(self, symbol: str, side: str, quantity: Decimal) -> FuturesFill:
        """@brief Fills a market order at the book and moves the account."""
        bid, ask = self._market.best_bid_ask(symbol)
        return self.fill_at(symbol, side, quantity, ask if side == _SIDE_BUY else bid)

    def fill_at(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        fee_rate: Decimal = TAKER_FEE_RATE,
    ) -> FuturesFill:
        """@brief Fills at `price`: the account rule `fill_market` applies,
        open to a test that needs fills at different prices. A resting order that
        traded pays `MAKER_FEE_RATE`."""
        signed = quantity if side == _SIDE_BUY else -quantity
        commission = quantity * price * fee_rate
        realized = self._move_position(symbol, signed, price)
        self._wallet += realized - commission
        return FuturesFill(price, quantity, commission, realized)

    def position_amount(self, symbol: str) -> Decimal:
        position = self._positions.get(symbol)
        return position.amount if position else Decimal(0)

    def open_symbols(self) -> list[str]:
        return list(self._positions)

    def entry_price(self, symbol: str) -> Decimal:
        return self._positions[symbol].entry_price

    def unrealized_pnl(self, symbol: str) -> Decimal:
        return self._unrealized(symbol) if symbol in self._positions else Decimal(0)

    def isolated(self, symbol: str) -> bool:
        return self._symbol_config.margin_type(symbol) == _ISOLATED

    def isolated_wallet(self, symbol: str) -> Decimal | None:
        """The margin behind `symbol`'s position under isolated margin; `None` under cross."""
        if not self.isolated(symbol) or symbol not in self._positions:
            return None
        return self._positions[symbol].isolated_margin

    @property
    def wallet_balance(self) -> Decimal:
        return self._wallet

    @property
    def cross_wallet(self) -> Decimal:
        """The wallet less every isolated margin: what the cross positions share."""
        isolated = sum(
            (
                self._positions[s].isolated_margin
                for s in self._positions
                if self.isolated(s)
            ),
            Decimal(0),
        )
        return self._wallet - isolated

    @property
    def available_balance(self) -> Decimal:
        margin = self._wallet + sum(
            (self._unrealized(s) for s in self._positions), Decimal(0)
        )
        return margin - sum(
            (self._initial_margin(s) for s in self._positions), Decimal(0)
        )

    def initial_margin(self, symbol: str) -> Decimal:
        return self._initial_margin(symbol) if symbol in self._positions else Decimal(0)

    def liquidation_price(self, symbol: str) -> Decimal | None:
        """Where the position is liquidated: on its isolated margin, or under cross
        on the wallet (the formula `futures_liquidation` documents)."""
        position = self._positions.get(symbol)
        if position is None:
            return None
        margin = position.isolated_margin if self.isolated(symbol) else self._wallet
        return futures_liquidation.liquidation_price(
            position.amount, position.entry_price, margin
        )

    def apply_funding(self, symbol: str, rate: Decimal) -> Decimal | None:
        """Charges one settlement at the mark: a long pays a positive rate, a short
        receives it. @return the signed wallet change, `None` for a flat symbol."""
        position = self._positions.get(symbol)
        if position is None:
            return None
        payment = -position.amount * self._market.mark_price(symbol) * rate
        self._wallet += payment
        return payment

    def liquidate(self, symbol: str, price: Decimal) -> FuturesFill:
        """Closes `symbol`'s whole position by force at `price`. Under isolated margin
        the whole margin behind it is lost (the worst case: no insurance fund and no
        clearance-fee schedule is modelled); under cross the loss is the realised PnL."""
        position = self._positions.pop(symbol)
        quantity = abs(position.amount)
        direction = 1 if position.amount > 0 else -1
        realized = (price - position.entry_price) * quantity * direction
        if self._symbol_config.margin_type(symbol) == _ISOLATED:
            self._wallet -= position.isolated_margin
        else:
            self._wallet += realized
        return FuturesFill(price, quantity, Decimal(0), realized)

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
        other = _BNB_MARGIN_USD if self.multi_assets else Decimal(0)
        assets = [
            {
                "asset": "USDT",
                "walletBalance": _q(self._wallet),
                "unrealizedProfit": _q(unrealized),
                "marginBalance": _q(margin),
                "initialMargin": _q(initial),
                "availableBalance": _q(available),
            }
        ]
        if self.multi_assets:
            assets.append(
                {
                    "asset": "BNB",
                    "walletBalance": "1.00000000",
                    "unrealizedProfit": "0.00000000",
                    "marginBalance": "1.00000000",
                    "initialMargin": "0.00000000",
                    "availableBalance": "1.00000000",
                }
            )
        return {
            # Binance's `GET /fapi/v2/account` carries the account's trading switch; the
            # pre-flight WARNs ("may trade was not reported") when an answer lacks it.
            "canTrade": True,
            "totalWalletBalance": _q(self._wallet + other),
            "totalUnrealizedProfit": _q(unrealized),
            "totalMarginBalance": _q(margin + other),
            "totalInitialMargin": _q(initial),
            "availableBalance": _q(available + other),
            "assets": assets,
            "positions": [
                {
                    "symbol": symbol,
                    "positionAmt": _q(position.amount),
                    "entryPrice": _q(position.entry_price),
                    "unrealizedProfit": _q(self._unrealized(symbol)),
                    "isolated": self.isolated(symbol),
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
            mark = self._market.mark_price(held)
            notional = position.amount * mark
            liquidation = self.liquidation_price(held)
            isolated = self.isolated(held)
            rows.append(
                {
                    "symbol": held,
                    "positionSide": "BOTH",
                    "positionAmt": _q(position.amount),
                    "entryPrice": _q(position.entry_price),
                    "breakEvenPrice": _q(position.entry_price),
                    "markPrice": _q(mark),
                    "unRealizedProfit": _q(self._unrealized(held)),
                    "liquidationPrice": _q(liquidation) if liquidation else "0",
                    "isolatedMargin": _q(position.isolated_margin) if isolated else "0",
                    "notional": _q(notional),
                    "marginAsset": "USDT",
                    "isolatedWallet": _q(position.isolated_margin) if isolated else "0",
                    "initialMargin": _q(self._initial_margin(held)),
                    "maintMargin": _q(
                        futures_liquidation.maintenance_margin(abs(notional))
                    ),
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
        leverage = self._symbol_config.leverage(symbol)
        if position is None or position.amount == 0:
            self._positions[symbol] = _Position(
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
            del self._positions[symbol]
        elif (remainder > 0) == (position.amount > 0):
            position.isolated_margin *= abs(remainder) / abs(position.amount)
            position.amount = remainder
        else:
            self._positions[symbol] = _Position(
                remainder, price, abs(remainder) * price / leverage
            )
        return realized

    def _unrealized(self, symbol: str) -> Decimal:
        position = self._positions[symbol]
        mark = self._market.mark_price(symbol)
        return (mark - position.entry_price) * position.amount

    def _initial_margin(self, symbol: str) -> Decimal:
        position = self._positions[symbol]
        notional = abs(position.amount) * self._market.mark_price(symbol)
        return notional / self._symbol_config.leverage(symbol)


def _q(value: Decimal) -> str:
    """Eight decimals, as Binance formats its account figures."""
    return f"{value:.8f}"
