"""`EPIC-034F` — which of a Grid's fields a verdict is about, and what the field says.

The Design step shows a violated constraint on the field that holds the
number to change, not only in a list of verdicts (decision D1): the user sees
"capital 10,000 is above the 9,999.99 USDT available" under Capital. The
mapping lives with the kind (`ui/kinds/grid/`), so the generic Bots screen
names no Grid field; it hands the kind's editor the verdicts and the editor
calls this.

Field keys are the definition's parameter names (`GridParams.to_config`).
A verdict that names no field says why in `NO_FIELD`, so a new constraint
cannot be added without deciding where it shows
(`test_grid_field_errors.py` holds the two tables to the constraint table).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

LOWER, UPPER = "lower", "upper"
GRID_COUNT, SPACING, CAPITAL = "grid_count", "spacing", "capital_quote"
STOP_LOSS, TAKE_PROFIT = "stop_loss", "take_profit"

#: What the editor labels each field.
FIELD_LABELS: Mapping[str, str] = MappingProxyType(
    {
        LOWER: "Lower price",
        UPPER: "Upper price",
        GRID_COUNT: "Grids",
        SPACING: "Spacing",
        CAPITAL: "Capital (quote)",
        STOP_LOSS: "Stop loss",
        TAKE_PROFIT: "Take profit",
    }
)

#: The field or fields to change, per violation code.
FIELDS_OF_CODE: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "EVERY_CYCLE_LOSES": (GRID_COUNT,),
        "SOME_GRIDS_LOSE": (GRID_COUNT,),
        "TOO_MANY_LEVELS": (GRID_COUNT,),
        "STEP_BELOW_MINIMUM": (GRID_COUNT,),
        "LEVEL_BELOW_MIN_NOTIONAL": (CAPITAL,),
        "LEVEL_ABOVE_MAX_NOTIONAL": (CAPITAL,),
        "CAPITAL_ABOVE_BALANCE": (CAPITAL,),
        "LEVEL_OUTSIDE_PRICE_BAND": (LOWER, UPPER),
        "RANGE_OUTSIDE_ATR_BAND": (LOWER, UPPER),
        "ARITHMETIC_ON_WIDE_RANGE": (SPACING,),
        "STOP_LOSS_INSIDE_RANGE": (STOP_LOSS,),
        "STOP_LOSS_DISTANCE": (STOP_LOSS,),
        "TAKE_PROFIT_INSIDE_RANGE": (TAKE_PROFIT,),
        "TAKE_PROFIT_DISTANCE": (TAKE_PROFIT,),
    }
)

#: Codes with no single field, and why.
NO_FIELD: Mapping[str, str] = MappingProxyType(
    {
        "KEY_CANNOT_TRADE": "it is about the API key, not a parameter",
        "PARAMETERS_NOT_SET": "its sentence names every parameter still unset",
        "PARAMETERS_UNREADABLE": "its sentence names the parameter it cannot read",
    }
)

BLOCKS = "Blocks Start: "
ADVICE = "Advice: "


@dataclass(frozen=True, slots=True)
class FieldError:
    """What one field says about itself."""

    text: str
    #: Whether Start waits on it (D7); words say so as well as the position.
    blocks: bool


def field_errors(verdicts: Iterable[Verdict]) -> dict[str, FieldError]:
    """The message of each field some verdict is about.

    A blocking verdict wins over advice on the same field, and the first of two
    of the same class stays, so the field shows the most urgent thing once.
    """
    shown: dict[str, FieldError] = {}
    for verdict in verdicts:
        if verdict.severity is VerdictSeverity.OK:
            continue
        error = FieldError(
            f"{BLOCKS if verdict.refuses else ADVICE}{verdict.reason}", verdict.refuses
        )
        for field in FIELDS_OF_CODE.get(verdict.code, ()):
            current = shown.get(field)
            if current is None or (error.blocks and not current.blocks):
                shown[field] = error
    return shown


def field_of_code(code: str) -> str | None:
    """The field to bring forward for a verdict code, or `None`."""
    fields = FIELDS_OF_CODE.get(code)
    return fields[0] if fields else None
