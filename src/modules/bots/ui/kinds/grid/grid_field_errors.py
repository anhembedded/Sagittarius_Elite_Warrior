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

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

LOWER, UPPER = "lower", "upper"
GRID_COUNT, SPACING, CAPITAL = "grid_count", "spacing", "capital_quote"
STOP_LOSS, TAKE_PROFIT = "stop_loss", "take_profit"
DIRECTION, LEVERAGE = "direction", "leverage"

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
        DIRECTION: "Direction",
        LEVERAGE: "Leverage",
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
        "LEVELS_ROUND_TO_ONE_PRICE": (GRID_COUNT, LOWER, UPPER),
        "ARITHMETIC_ON_WIDE_RANGE": (SPACING,),
        "STOP_LOSS_INSIDE_RANGE": (STOP_LOSS,),
        "STOP_LOSS_DISTANCE": (STOP_LOSS,),
        "TAKE_PROFIT_INSIDE_RANGE": (TAKE_PROFIT,),
        "TAKE_PROFIT_DISTANCE": (TAKE_PROFIT,),
        # A position venue's plan (`EPIC-039F`, shown by `EPIC-039J`).
        "LEVERAGE_ABOVE_CEILING": (LEVERAGE,),
        "LEVERAGE_HIGH": (LEVERAGE,),
        "NOTIONAL_ABOVE_BRACKET": (LEVERAGE, CAPITAL),
        "MARGIN_TOO_SMALL": (CAPITAL, LEVERAGE),
        "LIQUIDATION_INSIDE_RANGE": (LEVERAGE,),
        "STOP_LOSS_NEEDED": (STOP_LOSS, TAKE_PROFIT),
        "STOP_LOSS_AFTER_LIQUIDATION": (STOP_LOSS, TAKE_PROFIT),
        "STOP_LOSS_NEAR_LIQUIDATION": (STOP_LOSS, TAKE_PROFIT),
    }
)

#: The exit that closes a side of a NEUTRAL grid at a loss, by the verdict's `subject`: the long
#: side's is the stop loss below the range, the short side's the take profit above it
#: (`futures_grid_checks.py`). A LONG or SHORT grid has the stop loss alone. A code in
#: `EXIT_CODES` marks only that exit's field when its verdict names the side.
EXIT_OF_SIDE: Mapping[str, str] = MappingProxyType(
    {"long": STOP_LOSS, "short": TAKE_PROFIT}
)
EXIT_CODES = frozenset(
    {"STOP_LOSS_NEEDED", "STOP_LOSS_AFTER_LIQUIDATION", "STOP_LOSS_NEAR_LIQUIDATION"}
)

#: Codes with no single field, and why.
NO_FIELD: Mapping[str, str] = MappingProxyType(
    {
        "KEY_CANNOT_TRADE": "it is about the API key, not a parameter",
        "FOREIGN_OPEN_ORDERS": "it is about orders already open, not a parameter",
        "FUNDING_ADVERSE": "it is about the venue's funding rate and the direction, not one field",
        "CROSS_MARGIN_UNSUPPORTED": "the margin mode is the symbol's setting on the exchange, shown read-only",
        "LIQUIDATION_ESTIMATE": "it is the Liquidation row's figure, not a problem with a field",
        "PARAMETERS_NOT_SET": "its sentence names every parameter still unset",
        "PARAMETERS_UNREADABLE": "its sentence names the parameter it cannot read",
    }
)

BLOCKS = "Blocks Start: "
ADVICE = "Advice: "


@dataclass(frozen=True, slots=True)
class FieldError:
    """What one field says about itself."""

    #: One line (`Verdict.summary`, else its reason), `BOT-209`.
    text: str
    #: Whether Start waits on it (D7); words say so as well as the position.
    blocks: bool
    #: The whole sentence, for the field's tooltip.
    full: str = ""
    #: The grid count that clears it, offered as a button under the Grids field; `0` for none.
    use_grids: int = 0


def field_errors(
    verdicts: Iterable[Verdict], direction: TradeDirection = TradeDirection.LONG
) -> dict[str, FieldError]:
    """The message of each field some verdict is about.

    A blocking verdict wins over advice on the same field, and the first of two
    of the same class stays, so the field shows the most urgent thing once. A verdict
    about several fields (both bounds of the range) is told once, under the first, the one
    to change first (`BUG-210`): the same sentence under each read as two problems.
    """
    shown: dict[str, FieldError] = {}
    for verdict in verdicts:
        if verdict.severity is VerdictSeverity.OK:
            continue
        prefix = BLOCKS if verdict.refuses else ADVICE
        error = FieldError(
            f"{prefix}{verdict.summary or verdict.reason}",
            verdict.refuses,
            f"{prefix}{verdict.reason}",
            _suggested_grids(verdict),
        )
        for field in _fields_of(verdict, direction)[:1]:
            current = shown.get(field)
            if current is None or (error.blocks and not current.blocks):
                shown[field] = error
    return shown


def _suggested_grids(verdict: Verdict) -> int:
    """The grid count a check proposes when it is about the count (`BOT-209`)."""
    if GRID_COUNT not in FIELDS_OF_CODE.get(verdict.code, ()):
        return 0
    return int(verdict.numbers.get("suggested_grids", 0))


def _fields_of(verdict: Verdict, direction: TradeDirection) -> tuple[str, ...]:
    """The fields a verdict marks: an exit verdict that names its side marks that side's exit,
    which is the direction's: a LONG or SHORT grid has one loss exit, its stop loss; a NEUTRAL
    one ends its short side at the take profit over the range (`EPIC-039I`)."""
    if verdict.code in EXIT_CODES and verdict.subject in EXIT_OF_SIDE:
        if direction is not TradeDirection.NEUTRAL:
            return (STOP_LOSS,)
        return (EXIT_OF_SIDE[verdict.subject],)
    return FIELDS_OF_CODE.get(verdict.code, ())


def field_of_code(code: str) -> str | None:
    """The field to bring forward for a verdict code, or `None`."""
    fields = FIELDS_OF_CODE.get(code)
    return fields[0] if fields else None
