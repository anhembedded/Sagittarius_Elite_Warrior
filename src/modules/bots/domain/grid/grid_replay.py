"""`EPIC-029D` — one Grid's ladder, replayed step by step (ADR §3.2, D14).

The live executor's own reactions decide what a fill means: `runtime_from_plan`,
`ladder_orders`, `sells_net_of_opening_fee`, `on_fill`, `book_market_fill` and
`crossed_exit` are the functions `GridExecutor` calls. A backtest and a live
bot therefore agree on the counter order, the inventory, the cycle profit and
the halts; only *when* an order fills is the backtest's own (`grid_fill_rule`).

What the replay adds is what the exchange would have done:
· **The opening buy** at the first candle's open, at the taker fee taken in
  base, then the ladder net of that fee — the live start (ADR §3.1).
· **Fills** at the level's price and the maker fee: in base for a BUY, in
  quote for a SELL, as Binance Spot charges without BNB.
· **Exits** sell the whole inventory at market, at the taker fee: a stop loss
  at the stop price, or at the step's open when the price opened through it;
  a take profit the same way upward. The ladder's orders are cancelled.
· **Cash** in the quote asset, so equity is cash plus base at the close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    BacktestFill,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    Leg,
    PriceBar,
    PriceStep,
    buy_fills,
    sell_fills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    ladder_orders,
    runtime_from_plan,
    sells_net_of_opening_fee,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    LevelState as DrawnState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    Halt,
    LevelFill,
    PlaceOrder,
    accepted,
    book_market_fill,
    on_fill,
    placed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ROUNDING = OrderQuantityRoundingPolicy()
_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class ReplaySetup:
    """The user's parameters and the exchange's terms a replay runs under."""

    params: GridParams
    terms: ExchangeTerms


class GridReplay:
    """@brief The ladder, its cash and its fills, advanced one step at a time."""

    def __init__(self, setup: ReplaySetup, first: PriceBar) -> None:
        self._params = setup.params
        self._terms = setup.terms
        self.plan: GridPlan = plan(setup.params, setup.terms, first.open)
        self.runtime: GridRuntime = runtime_from_plan(self.plan, setup.terms.step_size)
        self.cash = setup.params.capital_quote
        self.fills: list[BacktestFill] = []
        self.maker_fees = _ZERO
        self.taker_fees = _ZERO
        self.stop: StopReason | None = None
        self.stop_detail = ""
        self._step = 0
        self._ids = 0
        self._active_from: dict[str, int] = {}
        self._open(first)

    # -- what the simulator reads ---------------------------------------- #

    def value_at(self, price: Decimal) -> Decimal:
        return self.cash + self.runtime.inventory * price

    def may_trade_in(self, low: Decimal, high: Decimal) -> bool:
        """Could a candle spanning `low`–`high` fill an order or cross an exit?

        Lets the replay skip a candle's 1-second klines when nothing rests
        within its range, which is most candles of a week."""
        tick = self._terms.tick_size
        for level in self.runtime.levels:
            order = level.order
            if order is None:
                continue
            if order.side is OrderSide.BUY and buy_fills(order.price, low, tick):
                return True
            if order.side is OrderSide.SELL and sell_fills(order.price, high, tick):
                return True
        stop_loss = self._params.stop_loss_price
        take_profit = self._params.take_profit_price
        return (stop_loss is not None and low <= stop_loss) or (
            take_profit is not None and high >= take_profit
        )

    def drawn_states(self) -> tuple[tuple[int, DrawnState], ...]:
        """Each level as the chart draws it; every level empty after an exit."""
        return tuple((level.index, self._drawn(level)) for level in self.runtime.levels)

    # -- advancing --------------------------------------------------------- #

    def run_step(self, step: PriceStep) -> None:
        self._step += 1
        for leg in step.legs:
            if self.stop is not None:
                return
            if leg is Leg.DOWN:
                self._down(step)
            else:
                self._up(step)

    def _open(self, first: PriceBar) -> None:
        quantity = self.plan.opening_buy_quantity
        if quantity > 0:
            fee_base = quantity * self._terms.taker_fee
            fill = LevelFill("open", first.open, quantity, base_fee=fee_base)
            self.runtime = book_market_fill(self.runtime, OrderSide.BUY, fill)
            self.cash -= first.open * quantity
            self._record(
                BacktestFill(
                    first.time,
                    OrderSide.BUY,
                    first.open,
                    quantity,
                    fee_base * first.open,
                    level_index=None,
                    maker=False,
                )
            )
        laid = sells_net_of_opening_fee(
            self.plan, self._terms.taker_fee, self._terms.step_size
        )
        for action in ladder_orders(laid):
            self._place(action, active_from=0)

    def _down(self, step: PriceStep) -> None:
        stop_loss = self._params.stop_loss_price
        hit = stop_loss is not None and step.low <= stop_loss
        tick = self._terms.tick_size
        for level in sorted(self._resting(OrderSide.BUY), key=lambda lv: -lv.price):
            if not buy_fills(level.price, step.low, tick):
                break
            if hit and stop_loss is not None and level.price <= stop_loss:
                break
            self._fill(level, step.time)
            if self.stop is not None:
                return
        if hit and stop_loss is not None:
            self._exit(StopReason.STOP_LOSS, min(stop_loss, step.open), step.time)

    def _up(self, step: PriceStep) -> None:
        take_profit = self._params.take_profit_price
        hit = take_profit is not None and step.high >= take_profit
        tick = self._terms.tick_size
        for level in sorted(self._resting(OrderSide.SELL), key=lambda lv: lv.price):
            if not sell_fills(level.price, step.high, tick):
                break
            if hit and take_profit is not None and level.price >= take_profit:
                break
            self._fill(level, step.time)
            if self.stop is not None:
                return
        if hit and take_profit is not None:
            self._exit(StopReason.TAKE_PROFIT, max(take_profit, step.open), step.time)

    def _resting(self, side: OrderSide) -> list[RuntimeLevel]:
        """Levels whose order of `side` rests and was placed before this step."""
        return [
            level
            for level in self.runtime.levels
            if level.order is not None
            and level.order.side is side
            and self._active_from.get(level.order.client_order_id, 0) <= self._step
        ]

    def _fill(self, level: RuntimeLevel, at: datetime) -> None:
        order = level.order
        if order is None:
            return
        quantity = order.quantity - order.executed
        maker = self._terms.maker_fee
        if order.side is OrderSide.BUY:
            fee_base = quantity * maker
            fill = LevelFill(order.client_order_id, order.price, quantity, fee_base)
            self.cash -= order.price * quantity
            fee_quote = fee_base * order.price
        else:
            fee_quote = order.price * quantity * maker
            fill = LevelFill(
                order.client_order_id, order.price, quantity, quote_fee=fee_quote
            )
            self.cash += order.price * quantity - fee_quote
        self._record(
            BacktestFill(
                at, order.side, order.price, quantity, fee_quote, level.index, True
            )
        )
        reaction = on_fill(self.runtime, fill, self._terms.step_size, hold=False)
        self.runtime = reaction.runtime
        for action in reaction.actions:
            if isinstance(action, Halt):
                self.stop, self.stop_detail = StopReason.HALTED, action.detail
                return
            self._place(action, active_from=self._step + 1)

    def _exit(self, reason: StopReason, price: Decimal, at: datetime) -> None:
        quantity = _ROUNDING.round_quantity_down(
            self.runtime.inventory, self._terms.market_step
        )
        if quantity > 0:
            fee = price * quantity * self._terms.taker_fee
            fill = LevelFill("exit", price, quantity, quote_fee=fee)
            self.runtime = book_market_fill(self.runtime, OrderSide.SELL, fill)
            self.cash += price * quantity - fee
            self._record(
                BacktestFill(at, OrderSide.SELL, price, quantity, fee, None, False)
            )
        self.stop = reason

    def _place(self, action: PlaceOrder, active_from: int) -> None:
        self._ids += 1
        client_order_id = f"L{action.level_index}#{self._ids}"
        self.runtime = accepted(
            placed(self.runtime, action, client_order_id), client_order_id
        )
        self._active_from[client_order_id] = active_from

    def _record(self, fill: BacktestFill) -> None:
        if fill.maker:
            self.maker_fees += fill.fee_quote
        else:
            self.taker_fees += fill.fee_quote
        self.fills.append(fill)

    def _drawn(self, level: RuntimeLevel) -> DrawnState:
        order = level.order
        if order is None or self.stop in (StopReason.STOP_LOSS, StopReason.TAKE_PROFIT):
            return DrawnState.EMPTY
        if order.executed > 0:
            return DrawnState.PARTIAL
        if order.side is OrderSide.BUY:
            return DrawnState.RESTING_BUY
        return DrawnState.RESTING_SELL
