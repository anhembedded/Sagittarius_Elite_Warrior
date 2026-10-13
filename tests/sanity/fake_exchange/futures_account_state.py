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
`commissionRate` answers), a market fill the taker fee. What is held, and the margin
behind it, is `positions` (`futures_positions.py`); this class owns the wallet. `apply_funding`
charges a settlement (to the position's isolated margin too, under isolated margin, so it
moves the liquidation price as on Binance) and `liquidate` closes a position by force,
losing its whole isolated margin.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from . import futures_liquidation
from .futures_funding import FuturesFunding
from .futures_market import FuturesMarket
from .futures_positions import FuturesPositions
from .futures_symbol_config import FuturesSymbolConfig

TAKER_FEE_RATE = Decimal("0.0005")
MAKER_FEE_RATE = Decimal("0.0002")
_STARTING_WALLET = Decimal(15000)
#: The BNB margin a Multi-Assets account also counts, in USD.
_BNB_MARGIN_USD = Decimal(600)
_SIDE_BUY = "BUY"


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
        self._market = market or FuturesMarket(FuturesFunding())
        #: What is held, and the margin behind it.
        self.positions = FuturesPositions(symbol_config, self._market)
        self._wallet = _STARTING_WALLET
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
        realized = self.positions.move(symbol, signed, price)
        self._wallet += realized - commission
        return FuturesFill(price, quantity, commission, realized)

    @property
    def wallet_balance(self) -> Decimal:
        return self._wallet

    @property
    def cross_wallet(self) -> Decimal:
        """The wallet less every isolated margin: what the cross positions share."""
        return self._wallet - self.positions.total_isolated_margin()

    @property
    def available_balance(self) -> Decimal:
        margin = self._wallet + self.positions.total_unrealized()
        return margin - self.positions.total_initial_margin()

    def apply_funding(self, symbol: str, rate: Decimal) -> Decimal | None:
        """Charges one settlement at the mark: a long pays a positive rate, a short
        receives it. Under isolated margin the payment comes out of (or goes into) the
        position's own margin as well as the wallet, so the liquidation price moves.
        @return the signed wallet change, `None` for a flat symbol."""
        held = self.positions.amount(symbol)
        if held == 0:
            return None
        payment = -held * self._market.mark_price(symbol) * rate
        self._wallet += payment
        if self.positions.isolated(symbol):
            self.positions.add_margin(symbol, payment)
        return payment

    def liquidate(self, symbol: str, price: Decimal) -> FuturesFill:
        """Closes `symbol`'s whole position by force at `price`. Under isolated margin
        the whole margin behind it is lost (the worst case: no insurance fund and no
        clearance-fee schedule is modelled); under cross the loss is the realised PnL."""
        held = self.positions.amount(symbol)
        entry = self.positions.entry_price(symbol)
        isolated = self.positions.isolated(symbol)
        margin = self.positions.close(symbol)
        direction = 1 if held > 0 else -1
        realized = (price - entry) * abs(held) * direction
        if isolated:
            self._wallet -= margin
        else:
            self._wallet += realized
        return FuturesFill(price, abs(held), Decimal(0), realized)

    def account(self) -> dict[str, Any]:
        """`GET /fapi/v2/account`."""
        unrealized = self.positions.total_unrealized()
        initial = self.positions.total_initial_margin()
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
                    "positionAmt": _q(self.positions.amount(symbol)),
                    "entryPrice": _q(self.positions.entry_price(symbol)),
                    "unrealizedProfit": _q(self.positions.unrealized(symbol)),
                    "isolated": self.positions.isolated(symbol),
                    "positionSide": "BOTH",
                }
                for symbol in self.positions.symbols()
            ],
        }

    def position_risk(self, symbol: str | None) -> list[dict[str, Any]]:
        """`GET /fapi/v3/positionRisk`: one row per open position, the v3
        shape (no `leverage` or `marginType` field, `BUG-114`); `notional`
        is signed, negative for a short, as Binance sends it."""
        rows = []
        for held in self.positions.symbols():
            if symbol is not None and held != symbol:
                continue
            amount = self.positions.amount(held)
            entry = self.positions.entry_price(held)
            mark = self._market.mark_price(held)
            notional = amount * mark
            liquidation = self.positions.liquidation_price(held, self._wallet)
            isolated = self.positions.isolated_margin(held)
            initial = self.positions.initial_margin(held)
            rows.append(
                {
                    "symbol": held,
                    "positionSide": "BOTH",
                    "positionAmt": _q(amount),
                    "entryPrice": _q(entry),
                    "breakEvenPrice": _q(entry),
                    "markPrice": _q(mark),
                    "unRealizedProfit": _q(self.positions.unrealized(held)),
                    "liquidationPrice": _q(liquidation) if liquidation else "0",
                    "isolatedMargin": _q(isolated) if isolated is not None else "0",
                    "notional": _q(notional),
                    "marginAsset": "USDT",
                    "isolatedWallet": _q(isolated) if isolated is not None else "0",
                    "initialMargin": _q(initial),
                    "maintMargin": _q(
                        futures_liquidation.maintenance_margin(abs(notional))
                    ),
                    "positionInitialMargin": _q(initial),
                    "openOrderInitialMargin": "0",
                    "adl": 1,
                    "bidNotional": "0",
                    "askNotional": "0",
                    "updateTime": 0,
                }
            )
        return rows


def _q(value: Decimal) -> str:
    """Eight decimals, as Binance formats its account figures."""
    return f"{value:.8f}"
