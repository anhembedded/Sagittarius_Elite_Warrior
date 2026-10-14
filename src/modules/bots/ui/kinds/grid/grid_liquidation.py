"""`EPIC-039J` — the Liquidation row of a Futures Grid's editor, from the guard's verdicts.

The guard (`futures_grid_checks.py`) is the single source of the figure: this module only
reads the verdicts it returned, per side (`Verdict.subject`), and words them. It never
estimates anything, so the screen cannot disagree with the verdict list under it, and a side
the guard did not judge has no line rather than a zero.

Every line says *estimate* (the exchange's own figure decides, `domain-truth-rule.md`), says
what it means for Start in words (`Blocks Start:` / `Advice:`, never colour alone), and names
the distance to the exit that closes the side when the guard measured it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_errors import (
    ADVICE,
    BLOCKS,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

#: What the row says before the guard has judged a plan.
NOT_ESTIMATED = (
    "Not estimated yet: it needs the plan's parameters and the symbol's brackets."
)

#: The sides in the order the row lists them: a Neutral plan shows both.
SIDES: tuple[str, ...] = ("long", "short")

_PRICE_KEY, _EXIT_KEY, _GAP_KEY = "liquidation_price", "exit_price", "gap"

#: The codes that carry a side's liquidation price, in the order they are trusted.
_ABOUT_LIQUIDATION = frozenset(
    {
        "LIQUIDATION_ESTIMATE",
        "LIQUIDATION_INSIDE_RANGE",
        "STOP_LOSS_AFTER_LIQUIDATION",
        "STOP_LOSS_NEAR_LIQUIDATION",
        "STOP_LOSS_NEEDED",
    }
)

_RANK: Mapping[VerdictSeverity, int] = MappingProxyType(
    {VerdictSeverity.OK: 0, VerdictSeverity.WARNING: 1, VerdictSeverity.REFUSED: 2}
)


@dataclass(frozen=True, slots=True)
class LiquidationLine:
    """One side of the plan: its words, and how serious the guard found it."""

    side: str
    text: str
    severity: VerdictSeverity


def liquidation_lines(verdicts: Iterable[Verdict]) -> tuple[LiquidationLine, ...]:
    """A line for each side the guard judged, `long` before `short`; `()` when it judged none."""
    lines = []
    for side in SIDES:
        about = [
            v for v in verdicts if v.subject == side and v.code in _ABOUT_LIQUIDATION
        ]
        if about:
            lines.append(_line(side, about))
    return tuple(lines)


def _line(side: str, about: list[Verdict]) -> LiquidationLine:
    worst = max(about, key=lambda verdict: _RANK[verdict.severity])
    price = _number(about, _PRICE_KEY)
    exit_price = _number(about, _EXIT_KEY)
    gap = _number(about, _GAP_KEY)
    figure = (
        f"liquidation near {_price(price)} (estimate)"
        if price is not None
        else "no estimate shown, see the verdicts"
    )
    where = ""
    if gap is not None and exit_price is not None:
        where = f", {_price(gap)} before the exit at {_price(exit_price)}"
    elif exit_price is not None:
        where = f", the exit at {_price(exit_price)} is beyond it"
    text = f"{_prefix(worst)}{side.capitalize()}: {figure}{where}"
    return LiquidationLine(side, text, worst.severity)


def _prefix(verdict: Verdict) -> str:
    if verdict.severity is VerdictSeverity.REFUSED:
        return BLOCKS
    if verdict.severity is VerdictSeverity.WARNING:
        return ADVICE
    return ""


def _number(about: Iterable[Verdict], key: str) -> Decimal | None:
    for verdict in about:
        if key in verdict.numbers:
            return verdict.numbers[key]
    return None


def _price(value: Decimal) -> str:
    return write_value(ColumnKind.PRICE, value)
