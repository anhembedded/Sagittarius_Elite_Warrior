"""`BOT-235` - the Plan's two estimated rows, as text: what the stop loss costs and what the take profit earns.

The numbers are `domain/grid/grid_exit_estimate.py`'s; this file only writes them with the
application's formatter and says, beside each, the path it assumed and what it leaves out, so a
figure is never read as a promise. Pure, so each sentence is tested without a widget.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    signed_percent_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exit_estimate import (
    ExitEstimate,
    ExitEstimates,
)
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
    "funding and slippage are left out."
)


@dataclass(frozen=True, slots=True)
class ExitRows:
    """The text of each row, empty where that exit is off, and the tone of each figure."""

    loss_at_stop: str = ""
    gain_at_take_profit: str = ""
    tones: Mapping[str, Tone] = field(default_factory=dict)


def exit_rows(estimates: ExitEstimates | None) -> ExitRows:
    if estimates is None:
        return ExitRows()
    stop, take = estimates.at_stop_loss, estimates.at_take_profit
    return ExitRows(
        loss_at_stop=_text(stop, estimates.capital) if stop else "",
        gain_at_take_profit=_text(take, estimates.capital) if take else "",
        tones={
            **({LOSS_AT_STOP_KEY: sign_tone(stop.net)} if stop else {}),
            **({GAIN_AT_TAKE_PROFIT_KEY: sign_tone(take.net)} if take else {}),
        },
    )


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
    return f"{run}; the {abs(held)} left is {closing} at {end}."
