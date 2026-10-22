"""`BOT-235` - what a Grid is worth when the price runs straight to its stop loss or take profit.

@details The business promise (the owner's question on the Plan): "if the stop loss hits, how much
do I lose; if the bot runs straight up to the take profit, how much do I make". Each figure is
worked by hand in its test from the ladder BNBUSDT 730-750 makes with 10 grids and 400 reached
(200 capital at 2x): levels 730, 732, ..., 750 at 2 apart, the price at 740 leaving that level
empty, five BUYs (730-738) and five SELLs (742-750), every order 0.05 BNB (40 / 750 rounded down to
the 0.01 step). Fees: maker 0.02%, taker 0.04%.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exit_estimate import (
    ExitEstimates,
    exit_estimates_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    model_position_along,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

D = Decimal
_TERMS = ExchangeTerms(
    tick_size=D("0.01"),
    step_size=D("0.01"),
    min_notional=D(5),
    maker_fee=D("0.0002"),
    taker_fee=D("0.0004"),
    max_notional_per_order=D(100_000),
    max_open_orders=200,
)
_FUTURES = ExposureLimits(frozenset(TradeDirection), 125, ExposureKind.POSITION)
_BNB = {
    "lower": "730",
    "upper": "750",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "200",
    "stop_loss": "price:721",
    "take_profit": "price:757",
    "direction": "LONG",
    "leverage": "2",
}


def _estimates(**changes: str) -> ExitEstimates:
    inputs = BotKindInputs(
        {**_BNB, **changes}, _TERMS, MarketView(D(740)), limits=_FUTURES
    )
    found = exit_estimates_for(inputs)
    assert found is not None
    return found


def test_a_long_losing_at_the_stop_pays_for_the_whole_ladder_marked_to_the_stop() -> (
    None
):
    """Hand-worked. The price falls 740 -> 721 through the BUYs 738, 736, 734, 732, 730.
    Held: the opening 0.25 at 740 (cost 185) + 5 x 0.05 at 3670 / 5 (cost 183.5) = 0.5 at 737.
    Closed at 721: 0.5 x (721 - 737) = -8.00. Fees: opening taker 185 x 0.0004 = 0.074, five
    maker fills 183.5 x 0.0002 = 0.0367, the close 0.5 x 721 x 0.0004 = 0.1442; total 0.2549.
    Net -8.2549, 4.12745% of the 200."""
    stop = _estimates().at_stop_loss

    assert stop is not None
    assert (stop.filled_side, stop.filled_levels) == (OrderSide.BUY, 5)
    assert stop.closed_quantity == D("0.5")
    assert stop.gross == D("-8.00")
    assert stop.fees == D("0.2549")
    assert stop.net == D("-8.2549")
    assert stop.net / _estimates().capital == D("-0.041274500")


def test_a_long_running_straight_to_the_take_profit_earns_only_its_sells() -> None:
    """Hand-worked. The price rises 740 -> 757 through the SELLs 742, 744, 746, 748, 750, each
    0.05 and each closing part of the opening 0.25 at 740: 0.05 x (3730 - 5 x 740) = 1.50.
    Nothing is left at 757. Fees: opening 0.074 + five maker fills 186.5 x 0.0002 = 0.0373.
    Net 1.3887: past the last SELL the ladder holds nothing, so the take profit adds none."""
    take = _estimates().at_take_profit

    assert take is not None
    assert (take.filled_side, take.filled_levels) == (OrderSide.SELL, 5)
    assert take.closed_quantity == 0
    assert take.gross == D("1.50")
    assert take.fees == D("0.1113")
    assert take.net == D("1.3887")


def test_a_short_mirrors_the_long() -> None:
    """Hand-worked, SHORT with the stop at 759 and the take profit at 723. Opening: sell 0.25
    at 740. Rising to 759 fills the SELLs 742-750 (0.25 more at 3730 / 5 = 746): short 0.5 at
    743, bought back at 759: 0.5 x (743 - 759) = -8.00; fees 0.074 + 186.5 x 0.0002 (0.0373)
    + 0.5 x 759 x 0.0004 (0.1518) = 0.2631; net -8.2631. Falling to 723 fills the BUYs 738-730,
    each covering 0.05 of the 0.25 short from 740: 0.05 x (5 x 740 - 3670) = 1.50; fees 0.074
    + 183.5 x 0.0002 (0.0367) = 0.1107; net 1.3893."""
    estimates = _estimates(
        direction="SHORT", stop_loss="price:759", take_profit="price:723"
    )

    assert estimates.at_stop_loss is not None
    assert estimates.at_stop_loss.filled_side is OrderSide.SELL
    assert estimates.at_stop_loss.closed_quantity == D("-0.5")
    assert estimates.at_stop_loss.net == D("-8.2631")
    assert estimates.at_take_profit is not None
    assert estimates.at_take_profit.filled_side is OrderSide.BUY
    assert estimates.at_take_profit.closed_quantity == 0
    assert estimates.at_take_profit.net == D("1.3893")


def test_a_neutral_loses_on_each_leg_at_its_own_exit() -> None:
    """Hand-worked, NEUTRAL (no opening trade) with the stop at 721 and the take profit at 757.
    Falling fills the BUYs 738-730: long 0.25 at 734, sold at 721: 0.25 x (721 - 734) = -3.25;
    fees 183.5 x 0.0002 (0.0367) + 0.25 x 721 x 0.0004 (0.0721) = 0.1088; net -3.3588.
    Rising fills the SELLs 742-750: short 0.25 at 746, bought back at 757: 0.25 x (746 - 757)
    = -2.75; fees 186.5 x 0.0002 (0.0373) + 0.25 x 757 x 0.0004 (0.0757) = 0.113; net -2.863.
    The take-profit figure is a loss: a Neutral grid's short leg ends there."""
    estimates = _estimates(direction="NEUTRAL")

    assert estimates.at_stop_loss is not None
    assert estimates.at_stop_loss.net == D("-3.3588")
    assert estimates.at_take_profit is not None
    assert estimates.at_take_profit.closed_quantity == D("-0.25")
    assert estimates.at_take_profit.net == D("-2.8630")


def test_an_exit_that_is_off_has_no_estimate() -> None:
    estimates = _estimates(stop_loss="off", take_profit="off")

    assert estimates.at_stop_loss is None
    assert estimates.at_take_profit is None


def test_parameters_that_make_no_plan_have_no_estimate() -> None:
    inputs = BotKindInputs({**_BNB, "lower": ""}, _TERMS, MarketView(D(740)))

    assert exit_estimates_for(inputs) is None


@pytest.mark.parametrize("direction", ["LONG", "SHORT", "NEUTRAL"])
def test_the_estimate_books_the_same_fills_as_the_position_model(
    direction: str,
) -> None:
    """The profit before fees is the position model's, which the Futures replay books with: the
    straight path to each exit leaves that model the same position and realised profit (its
    open remainder marked to the exit)."""
    params = GridParams.from_config({**_BNB, "direction": direction})
    ladder = plan(params, _TERMS, D(740), LevelSizing.EQUAL_QUANTITY)
    estimates = _estimates(direction=direction)
    for estimate, exit_price in (
        (estimates.at_stop_loss, params.stop_loss_price),
        (estimates.at_take_profit, params.take_profit_price),
    ):
        assert estimate is not None
        assert exit_price is not None
        run = model_position_along(ladder, [exit_price])
        marked = (
            run.position * (exit_price - run.entry_price) if run.entry_price else D(0)
        )
        assert estimate.gross == run.realised + marked
        assert estimate.closed_quantity == run.position
