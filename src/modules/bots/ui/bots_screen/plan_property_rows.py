"""`BOT-206` — what the Plan's property table lists: its groups and, under each, its rows.

Data only. A row's key is the name of the `BotFacts` field or the `ladder_facts` row that writes
it; a row's title is the label the dock always had, except the Results titles, which are the
`BOT-229` constants of `run_earnings.py` (`REALISED_TITLE`, `TOTAL_SUM_TITLE`, ...) that `bot show`
prints too. The three readiness steps are rows too, keyed
by the step.

Extension cases: another group is one `PropertyGroup` in `PROPERTY_GROUPS`; another figure is one
`PropertyRow` in its group and one key in the facts that write it. The widget, `plan_property_grid.py`,
names no row.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    FEES_TITLE,
    FUNDING_TITLE,
    GRID_CYCLES_TITLE,
    REALISED_TITLE,
    TOTAL_SUM_TITLE,
    UNREALISED_TITLE,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: The rows only a venue with funding shows (`EPIC-039J`): costs apart from the profit.
COST_KEYS = ("commissions", "funding")
#: The row only a position venue shows (`BOT-193`): its liquidation price is the exchange's, not the record's.
LIQUIDATION_KEY = "liquidation"
#: The group a bot at rest shows and a bot with a run does not (`EPIC-034H`).
READINESS_GROUP = "readiness"
#: The group of the plan's figures, and its heading while they come from a design not saved
#: yet (`BUG-261`).
PLAN_GROUP = "plan"
PLAN_TITLE = "Plan"
PLAN_UNSAVED_TITLE = "Plan (not saved)"


@dataclass(frozen=True, slots=True)
class PropertyRow:
    key: str
    title: str
    #: What the value is: a word reads left, a figure right (`row_kind_delegate.py`), and a
    #: figure whose digits line up is in the platform's fixed-pitch font (`kind_font`).
    kind: ColumnKind = ColumnKind.TEXT


@dataclass(frozen=True, slots=True)
class PropertyGroup:
    key: str
    title: str
    rows: tuple[PropertyRow, ...]


def step_key(step: ReadinessStep) -> str:
    """The key of the row that says where `step` stands."""
    return f"step_{step.name.lower()}"


def _rows(*triples: tuple[str, str, ColumnKind]) -> tuple[PropertyRow, ...]:
    return tuple(PropertyRow(key, title, kind) for key, title, kind in triples)


_TEXT, _MONEY, _PRICE, _QUANTITY = (
    ColumnKind.TEXT,
    ColumnKind.MONEY,
    ColumnKind.PRICE,
    ColumnKind.QUANTITY,
)

PROPERTY_GROUPS: tuple[PropertyGroup, ...] = (
    PropertyGroup(
        READINESS_GROUP,
        "Readiness",
        _rows(*((step_key(step), step.value, _TEXT) for step in ReadinessStep)),
    ),
    PropertyGroup(
        PLAN_GROUP,
        PLAN_TITLE,
        _rows(
            ("venue", "Venue", _TEXT),
            ("symbol", "Symbol", _TEXT),
            ("capital", "Capital", _MONEY),
            # `BOT-193`: the ladder the parameters make (designed) and what a cycle there
            # earns (estimate). The parameters are the design on screen while it is not saved
            # (`BUG-261`), so the title no longer says "Saved".
            ("grid_step", "Grid step, top to bottom", ColumnKind.PERCENT),
            ("cycle_profit", "Profit per cycle (estimate)", _MONEY),
            ("lower_edge", "Lower edge", _PRICE),
            ("upper_edge", "Upper edge", _PRICE),
            ("stop_loss", "Stop loss", _PRICE),
            ("take_profit", "Take profit", _PRICE),
            (LIQUIDATION_KEY, "Liquidation price", _TEXT),
        ),
    ),
    PropertyGroup(
        "results",
        "Results",
        _rows(
            ("running_time", "Running time", ColumnKind.DURATION),
            # `BOT-229`: in the order that adds up. Realised, of which the grid cycles (a different
            # view of part of it), then what is held and valued, the costs, and the total.
            ("realised", REALISED_TITLE, _MONEY),
            ("grid_profit", GRID_CYCLES_TITLE, _MONEY),
            ("cycles", "Completed cycles", _QUANTITY),
            ("cycle_average", "Average per cycle (net of fees)", _MONEY),
            ("unrealised", UNREALISED_TITLE, _MONEY),
            ("commissions", FEES_TITLE, _QUANTITY),
            ("funding", FUNDING_TITLE, _QUANTITY),
            ("total_pnl", TOTAL_SUM_TITLE, _MONEY),
            ("hodl", "HODL benchmark", _MONEY),
            ("earnings_basis", "How to read these", _TEXT),
        ),
    ),
    PropertyGroup(
        "holdings",
        "Holdings",
        _rows(
            ("inventory", "Held", _QUANTITY),
            ("earlier_runs", "Left from earlier runs", _QUANTITY),
            # Beside what is held: where the price the bot last heard stands, and how old it is.
            ("last_price", "Last price heard", _PRICE),
        ),
    ),
)

#: Every row key, in the order the table lists them.
PROPERTY_KEYS: tuple[str, ...] = tuple(
    row.key for group in PROPERTY_GROUPS for row in group.rows
)
