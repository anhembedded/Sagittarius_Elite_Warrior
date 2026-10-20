"""`BOT-206` — what the Plan dock's property table lists: its groups and, under each, its rows.

Data only. A row's key is the name of the `BotFacts` field or the `ladder_facts` row that writes
it; a row's title is the label the dock always had (`run_earnings.TOTAL_PNL_BASIS` is
`BOT-202`'s wording and is spelled in no other place). The three readiness steps are rows too, keyed
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
    TOTAL_PNL_BASIS,
)

#: The rows only a venue with funding shows (`EPIC-039J`): costs apart from the profit.
COST_KEYS = ("commissions", "funding")
#: The row only a position venue shows (`BOT-193`): its liquidation price is the exchange's, not the record's.
LIQUIDATION_KEY = "liquidation"
#: The group a bot at rest shows and a bot with a run does not (`EPIC-034H`).
READINESS_GROUP = "readiness"


@dataclass(frozen=True, slots=True)
class PropertyRow:
    key: str
    title: str


@dataclass(frozen=True, slots=True)
class PropertyGroup:
    key: str
    title: str
    rows: tuple[PropertyRow, ...]


def step_key(step: ReadinessStep) -> str:
    """The key of the row that says where `step` stands."""
    return f"step_{step.name.lower()}"


def _rows(*pairs: tuple[str, str]) -> tuple[PropertyRow, ...]:
    return tuple(PropertyRow(key, title) for key, title in pairs)


PROPERTY_GROUPS: tuple[PropertyGroup, ...] = (
    PropertyGroup(
        READINESS_GROUP,
        "Readiness",
        _rows(*((step_key(step), step.value) for step in ReadinessStep)),
    ),
    PropertyGroup(
        "plan",
        "Plan",
        _rows(
            ("venue", "Venue"),
            ("symbol", "Symbol"),
            ("capital", "Capital"),
            # `BOT-193`: the ladder the saved parameters make (designed) and what a cycle there
            # earns (estimate).
            ("grid_step", "Saved grid step, top to bottom"),
            ("cycle_profit", "Profit per cycle (estimate)"),
            ("lower_edge", "Lower edge"),
            ("upper_edge", "Upper edge"),
            ("stop_loss", "Stop loss"),
            ("take_profit", "Take profit"),
            (LIQUIDATION_KEY, "Liquidation price"),
        ),
    ),
    PropertyGroup(
        "results",
        "Results",
        _rows(
            ("running_time", "Running time"),
            ("grid_profit", "Profit from completed cycles"),
            ("cycles", "Completed cycles"),
            ("cycle_average", "Average per cycle (net of fees)"),
            ("total_pnl", f"Total PnL ({TOTAL_PNL_BASIS})"),
            ("unrealised", "of which unrealised"),
            ("hodl", "HODL benchmark"),
            ("commissions", "Commissions paid"),
            ("funding", "Funding (earned +, paid −)"),
        ),
    ),
    PropertyGroup(
        "holdings",
        "Holdings",
        _rows(
            ("inventory", "Held"),
            ("earlier_runs", "Left from earlier runs"),
            # Beside what is held: where the price the bot last heard stands, and how old it is.
            ("last_price", "Last price heard"),
        ),
    ),
)

#: Every row key, in the order the table lists them.
PROPERTY_KEYS: tuple[str, ...] = tuple(
    row.key for group in PROPERTY_GROUPS for row in group.rows
)
