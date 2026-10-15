"""`EPIC-029F` — the small parts of the Grid editor that are not its layout: a decimal field, the
offer a suggestion action makes, a whole number read from text. Apart from `grid_panel.py`
(the widgets and their wiring) so that file stays one level of abstraction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLineEdit
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
    SuggestedRange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_suggestion import (
    PlanSuggestion,
    SuggestionRequest,
    suggest_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)

_NO_RANGE_YET = "The planner has no {name} range: it needs more stored daily candles."


def decimal_field(name: str) -> QLineEdit:
    field = QLineEdit()
    field.setObjectName(name)
    return field


def offer_suggestion(
    action: QAction, suggested: SuggestedRange | None, name: str
) -> None:
    action.setEnabled(suggested is not None)
    if suggested is None:
        action.setToolTip(_NO_RANGE_YET.format(name=name))
    else:
        action.setToolTip(
            f"Write the plan for the range {suggested.lower} – {suggested.upper}: "
            "a price exit that no longer fits moves, and the editor says which."
        )


def int_or(text: str, default: int) -> int:
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class EditedPlan:
    """The parameters as the fields hold them now, and what the venue allows them."""

    config: Mapping[str, str]
    limits: ExposureLimits


def suggest_for(
    source: str,
    band: SuggestedRange | None,
    market: PlannerMarket | None,
    edited: EditedPlan,
) -> PlanSuggestion | None:
    """The plan `source`'s `band` makes of the edited parameters; `None` while the planner
    has no band or has not read the venue (`BUG-211`)."""
    if band is None or market is None or market.terms is None or market.market is None:
        return None
    inputs = BotKindInputs(
        edited.config, market.terms, market.market, limits=edited.limits
    )
    return suggest_plan(
        SuggestionRequest(source, band.lower, band.upper, inputs, GridThresholds())
    )
