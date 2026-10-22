"""`BOT-235` - the Plan's two estimated rows, as text: what the stop loss costs and what the take profit earns.

The numbers are `domain/grid/grid_exit_estimate.py`'s; this file only writes them with the
application's formatter and says, beside each, the path it assumed and what it leaves out, so a
figure is never read as a promise. Pure, so each sentence is tested without a widget.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    signed_percent_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exit_estimate import (
    ExitEstimate,
    ExitEstimates,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    sign_tone,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    signed_key,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

LOSS_AT_STOP_KEY = "loss_at_stop"
GAIN_AT_TAKE_PROFIT_KEY = "gain_at_take_profit"
#: What both estimates leave out, said beside each figure.
LEFT_OUT = (
    "Fees are in (maker on the ladder, taker on the opening and the closing trade); "
    "funding, slippage and a liquidation before the exit are left out (the checks judge that)."
)
#: Said instead of a figure that cannot happen: the plan guard refused the exit because the
#: position is liquidated first, so the margin is lost before the exit is reached.
LIQUIDATION_FIRST = (
    "Not reached: the position would be liquidated before this exit, so its margin is lost "
    "first (see the Liquidation price and the Checks)."
)
_EXIT_AFTER_LIQUIDATION = "STOP_LOSS_AFTER_LIQUIDATION"


@dataclass(frozen=True, slots=True)
class ExitRows:
    """The text of each row, empty where that exit is off, and the tone of each figure."""

    loss_at_stop: str = ""
    gain_at_take_profit: str = ""
    tones: Mapping[str, Tone] = field(default_factory=dict)


def exit_rows(
    estimates: ExitEstimates | None, cut_by_liquidation: frozenset[str] = frozenset()
) -> ExitRows:
    """@param cut_by_liquidation the row keys whose exit the position is liquidated before
    (`rows_cut_by_liquidation`): they say so instead of a figure that cannot happen."""
    if estimates is None:
        return ExitRows()
    stop, take = estimates.at_stop_loss, estimates.at_take_profit
    return ExitRows(
        loss_at_stop=_row(
            stop, estimates.capital, LOSS_AT_STOP_KEY in cut_by_liquidation
        ),
        gain_at_take_profit=_row(
            take, estimates.capital, GAIN_AT_TAKE_PROFIT_KEY in cut_by_liquidation
        ),
        tones={
            key: sign_tone(estimate.net)
            for key, estimate in (
                (LOSS_AT_STOP_KEY, stop),
                (GAIN_AT_TAKE_PROFIT_KEY, take),
            )
            if estimate and key not in cut_by_liquidation
        },
    )


def rows_cut_by_liquidation(
    verdicts: Iterable[Verdict], direction: TradeDirection
) -> frozenset[str]:
    """The rows whose exit the guard refused as beyond the liquidation price. The stop loss
    closes the long leg of a LONG or NEUTRAL grid and the short leg of a SHORT grid; a NEUTRAL
    grid's short leg closes at the take profit (`futures_grid_checks._loss_exit`)."""
    sides = {v.subject for v in verdicts if v.code == _EXIT_AFTER_LIQUIDATION}
    stop_side = "short" if direction is TradeDirection.SHORT else "long"
    cut = {LOSS_AT_STOP_KEY} if stop_side in sides else set()
    if direction is TradeDirection.NEUTRAL and "short" in sides:
        cut.add(GAIN_AT_TAKE_PROFIT_KEY)
    return frozenset(cut)


def _row(estimate: ExitEstimate | None, capital: Decimal, cut: bool) -> str:
    if estimate is None:
        return ""
    return LIQUIDATION_FIRST if cut else _text(estimate, capital)


def _text(estimate: ExitEstimate, capital: Decimal) -> str:
    money = write_value(ColumnKind.MONEY, float(estimate.net), signed_key("pnl"))
    share = signed_percent_of(estimate.net / capital)
    return f"{money} ({share} of capital). {_path(estimate)} {LEFT_OUT}"


def _path(estimate: ExitEstimate) -> str:
    """The run assumed: where the price goes, what fills on the way and what closes at the end."""
    start = write_value(ColumnKind.PRICE, estimate.start_price)
    end = write_value(ColumnKind.PRICE, estimate.exit_price)
    verb = "falls" if estimate.filled_side is OrderSide.BUY else "rises"
    orders = f"{estimate.filled_levels} {estimate.filled_side.value} orders"
    run = f"Straight run: the price {verb} from {start} to {end}, filling {orders}"
    held = estimate.closed_quantity
    if held == 0:
        return f"{run}; nothing is left to close there."
    closing = "sold" if held > 0 else "bought back"
    left = write_value(ColumnKind.QUANTITY, float(abs(held)))
    return f"{run}; the {left} left is {closing} at {end}."
