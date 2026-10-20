"""`BOT-193` — the lines the Ladder panel shows above its table, as text.

The words are `contracts/grid_ladder_texts.py`, which `bot show` uses too; this file only hands
them the Bots tab's own money and price writers (`write_value`, the application's formatter), so a
price reads here as it does in the Orders table beside it. Pure, so each line is tested without a
widget.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
    LadderUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    brief_summary_line,
    cycle_profit_text,
    position_texts,
    recorded_average_text,
    step_text,
    summary_line,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import NO_VALUE
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

NO_LADDER_YET = "Select a bot to see its ladder."
#: The Plan panel's rows that say the ladder and where the price stands (`plan_property_rows.PROPERTY_GROUPS`).
LADDER_ROWS = (
    "grid_step",
    "cycle_profit",
    "cycle_average",
    "last_price",
    "lower_edge",
    "upper_edge",
    "stop_loss",
    "take_profit",
    "liquidation",
)


def _price(value: Decimal) -> str:
    return write_value(ColumnKind.PRICE, value)


def _money(value: Decimal) -> str:
    return write_value(ColumnKind.MONEY, float(value))


@dataclass(frozen=True, slots=True)
class LadderFacts:
    """What the Bots mode says about the selected bot's ladder: one line for the Ladder panel and
    one text per Plan row."""

    #: The ladder in one short line; or why there is none.
    summary: str
    #: The same line with its reasons (the fee rate that is not saved), for the tooltip.
    detail: str = ""
    #: Why the grids' states are not shown; empty when they are.
    note: str = ""
    #: One text per `LADDER_ROWS` key; empty with no bot, `NO_VALUE` where there is no ladder.
    rows: Mapping[str, str] = field(default_factory=dict)
    #: Whether the venue has a liquidation price to say is unknown (the Plan row is hidden otherwise).
    shows_liquidation: bool = False


def ladder_facts(ladder: GridLadder | LadderUnavailable | None) -> LadderFacts:
    if ladder is None:
        return LadderFacts(NO_LADDER_YET, rows=dict.fromkeys(LADDER_ROWS, ""))
    if isinstance(ladder, LadderUnavailable):
        return LadderFacts(ladder.reason, rows=dict.fromkeys(LADDER_ROWS, NO_VALUE))
    position = position_texts(ladder.position, _price)
    return LadderFacts(
        summary=brief_summary_line(ladder.summary, _money),
        detail=summary_line(ladder.summary, _money),
        note=ladder.run_note,
        rows={
            "grid_step": step_text(ladder.summary),
            "cycle_profit": cycle_profit_text(ladder.summary, _money),
            "cycle_average": recorded_average_text(ladder.recorded, _money),
            "last_price": position.last_price,
            "lower_edge": position.lower_edge,
            "upper_edge": position.upper_edge,
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit,
            "liquidation": position.liquidation or "",
        },
        shows_liquidation=position.liquidation is not None,
    )
