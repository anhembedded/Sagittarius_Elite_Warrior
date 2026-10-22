"""`BOT-235` — what a Grid is worth if its price runs straight to the stop loss or to the take profit.

@details Two estimates, over the plan the bot would place, on the one position book the Futures
replay and the position model book their fills with (`PositionBook`, `grid_position_model.py`), so
the arithmetic of a fill is not written a second time:

  · **at the stop loss** — the price falls (rises, for a SHORT grid) from the plan's last price to
    the stop, nothing bouncing: every resting order on the way fills, which for a LONG grid is
    every BUY level, the largest position the ladder holds. The whole position is then closed at
    the stop;
  · **at the take profit** — the price runs from the last price to the take profit the other way:
    every SELL level fills (every BUY level, for a SHORT grid), the ladder's orders that close the
    opening position among them, and whatever is left is closed at the take profit.

A straight run never reaches a counter order (a BUY's counter SELL rests above the BUY, behind the
price), so the fills are the plan's own levels and the result does not depend on how the quantities
were sized: a Spot ladder and a position ladder are read the same way. On Spot the figure is
approximate, not exact: the Spot replay takes fees in base and nets the opening fee off the sells
(about 0.1% apart in a probe at a 0.1% fee). A NEUTRAL grid has no
opening trade and two legs, each ending at its own exit (`futures_grid_checks._loss_exit`): its
stop-loss estimate is the long leg and its take-profit estimate the short leg, which closes at a
price above everything it sold, so that estimate is a loss.

**Fees** follow `FuturesReplay`: the opening trade and the closing trade at the exit are taker
fills (`ExchangeTerms.taker_fee`), the ladder's fills are maker fills (`maker_fee`). **Left out,
and said so wherever the figure is shown:** funding (it depends on how long the price takes),
slippage on the market close, and a liquidation before the exit (the plan guard judges that:
`futures_grid_checks.py`).

@par Extension cases
  · another exit (a trailing stop): one more `ExitEstimate` on `ExitEstimates`, from `_run_to`;
  · a path through a given candle series is the replay's job, not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    entry_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exposure_check import (
    exposure_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
    unset_parameters,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridLevel,
    GridPlan,
    LevelSide,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    PositionBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


@dataclass(frozen=True, slots=True)
class ExitEstimate:
    """The result of one straight run, in the quote asset."""

    start_price: Decimal
    exit_price: Decimal
    #: The side of the ladder orders that fill on the way: BUY on a fall, SELL on a rise.
    filled_side: OrderSide
    #: How many ladder orders fill on the way.
    filled_levels: int
    #: The signed quantity closed at the exit (`+` a long sold, `-` a short bought back); zero
    #: when the ladder's own fills left nothing to close.
    closed_quantity: Decimal
    #: Profit booked by every closing fill on the way, before fees.
    gross: Decimal
    #: The opening trade's, the ladder fills' and the closing trade's commissions together.
    fees: Decimal

    @property
    def net(self) -> Decimal:
        return self.gross - self.fees


@dataclass(frozen=True, slots=True)
class ExitEstimates:
    """Both estimates and the capital they are a share of; `None` where that exit is off."""

    capital: Decimal
    direction: TradeDirection
    at_stop_loss: ExitEstimate | None
    at_take_profit: ExitEstimate | None


def exit_estimates_for(inputs: BotKindInputs) -> ExitEstimates | None:
    """The estimates of the plan a Start of `inputs` would place; `None` when the parameters
    make no plan (not set, unreadable, refused by the venue's exposure limits, or a value out
    of range), the same cases in which `evaluate_grid` has no plan."""
    if unset_parameters(inputs.config):
        return None
    try:
        params = GridParams.from_config(inputs.config)
    except GridParamsError:
        return None
    if exposure_refusal(params, inputs.limits) is not None:
        return None
    if params.grid_count > inputs.terms.max_open_orders:
        return None
    try:
        return estimate_exits(params, entry_plan(params, inputs), inputs.terms)
    except ArithmeticError:
        return None


def estimate_exits(
    params: GridParams, plan: GridPlan, terms: ExchangeTerms
) -> ExitEstimates:
    stop, take = params.stop_loss_price, params.take_profit_price
    return ExitEstimates(
        params.capital_quote,
        params.direction,
        None if stop is None else _run_to(plan, stop, terms),
        None if take is None else _run_to(plan, take, terms),
    )


def _run_to(plan: GridPlan, exit_price: Decimal, terms: ExchangeTerms) -> ExitEstimate:
    """The plan run from its last price straight to `exit_price`, then closed there."""
    book = PositionBook(plan.opening_quantity, plan.last_price)
    fees = abs(plan.opening_quantity) * plan.last_price * terms.taker_fee
    falling = exit_price < plan.last_price
    side = OrderSide.BUY if falling else OrderSide.SELL
    reached = _levels_reached(plan, exit_price, falling=falling)
    for level in reached:
        book.fill(side, level.quantity, level.price)
        fees += level.notional * terms.maker_fee
    held = book.position
    if held != 0:
        closing = OrderSide.SELL if held > 0 else OrderSide.BUY
        fees += abs(held) * exit_price * terms.taker_fee
        book.fill(closing, abs(held), exit_price)
    return ExitEstimate(
        plan.last_price, exit_price, side, len(reached), held, book.realised, fees
    )


def _levels_reached(
    plan: GridPlan, exit_price: Decimal, *, falling: bool
) -> list[GridLevel]:
    """The orders the price passes, in the order it passes them: the BUYs from the highest down
    on a fall, the SELLs from the lowest up on a rise (a level at the price itself fills)."""
    if falling:
        buys = [lv for lv in plan.levels if lv.side is LevelSide.BUY]
        return sorted(
            (lv for lv in buys if lv.price >= exit_price), key=lambda lv: -lv.price
        )
    sells = [lv for lv in plan.levels if lv.side is LevelSide.SELL]
    return sorted(
        (lv for lv in sells if lv.price <= exit_price), key=lambda lv: lv.price
    )
