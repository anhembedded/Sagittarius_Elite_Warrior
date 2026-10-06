"""The figures under one side of the order form, as a `Readout` (`EPIC-033N`).

Available, the most the side may order, the total, the fee and — on a Futures
desk — the cost and an estimated liquidation price. Each is written by the
application's formatter; its unit is in its title, because the unit follows
the symbol and the side ("Max buy (BTC)", "Max total (USDT)") while the
number is only a number. The order form used to write each figure as text
with `format_amount`, unit appended.

An amount in the quote asset is money, to the cent. The fee is a quantity:
a fee is often far below a cent, and money's two decimals would print it as
`0.00`. Until the side has figures every row is empty.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    SideFigures,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind, ColumnSpec

#: The key of the estimated liquidation price row, which carries a tooltip.
LIQUIDATION_KEY = "liquidation"


@dataclass(frozen=True)
class SideUnits:
    """What the figures of one side are counted in."""

    base: str
    quote: str
    #: The side's verb as the desk names it: "Buy", "Long".
    side_label: str
    futures: bool


def side_readout(figures: SideFigures | None, units: SideUnits) -> Readout:
    by_quote = figures is not None and figures.sized_by_quote
    available_asset = figures.available_asset if figures else units.quote
    available_kind = (
        ColumnKind.MONEY if available_asset == units.quote else ColumnKind.QUANTITY
    )
    maximum = (
        ColumnSpec("maximum", f"Max total ({units.quote})", ColumnKind.MONEY)
        if by_quote
        else ColumnSpec(
            "maximum",
            f"Max {units.side_label.lower()} ({units.base})",
            ColumnKind.QUANTITY,
        )
    )
    specs = [
        ColumnSpec("available", f"Available ({available_asset})", available_kind),
        maximum,
        ColumnSpec("total", f"Total ({units.quote})", ColumnKind.MONEY),
        ColumnSpec("fee", f"Est. fee ({units.quote})", ColumnKind.QUANTITY),
    ]
    if units.futures:
        specs += [
            ColumnSpec("cost", f"Cost ({units.quote})", ColumnKind.MONEY),
            ColumnSpec(LIQUIDATION_KEY, "Liq. price (est.)", ColumnKind.PRICE),
        ]
    if figures is None:
        return Readout(tuple(specs), {spec.key: None for spec in specs})
    liquidation = figures.liquidation.price if figures.liquidation else None
    values = {
        "available": figures.available,
        "maximum": figures.max_total if by_quote else figures.max_quantity,
        "total": figures.total,
        "fee": figures.fee,
        "cost": figures.cost,
        LIQUIDATION_KEY: liquidation,
    }
    return Readout(tuple(specs), {spec.key: values[spec.key] for spec in specs})
