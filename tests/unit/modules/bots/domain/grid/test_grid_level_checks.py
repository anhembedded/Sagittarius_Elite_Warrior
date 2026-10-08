"""`EPIC-035S` (audit L3) — levels that round to one price are refused.

Tick rounding can merge two levels. The ladder then holds two rungs at one
price, `GridRuntime.level_at` answers the first of them for either, and a fill
or an adopted order is booked on the wrong rung. The plan is refused before any
order, naming the colliding levels.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)

_CODES = ("LEVELS_ROUND_TO_ONE_PRICE", "LEVELS_DISTINCT")
#: A 0.05 range over 5 grids is 0.01 a step: on a 0.01 tick every level is
#: distinct; on a 0.05 tick (below) they merge.
_THIN = {
    "lower": "100",
    "upper": "100.05",
    "grid_count": "5",
    "capital_quote": "1000",
    "stop_loss": "off",
    "take_profit": "off",
}


def _verdicts(tick: str, **changes: str) -> tuple[Verdict, ...]:
    base = inputs(last_price=Decimal("100.02"), **{**_THIN, **changes})
    terms = replace(base.terms, tick_size=Decimal(tick))
    return evaluate_grid(replace(base, terms=terms), GridThresholds()).verdicts


def _find(verdicts: tuple[Verdict, ...]) -> Verdict | None:
    return next((v for v in verdicts if v.code in _CODES), None)


def test_two_levels_that_round_to_one_price_are_refused() -> None:
    verdict = _find(_verdicts("0.05"))

    assert verdict is not None
    assert verdict.severity is VerdictSeverity.REFUSED


def test_the_refusal_names_the_colliding_levels_and_the_next_action() -> None:
    verdict = _find(_verdicts("0.05"))

    assert verdict is not None
    assert "levels 0, 1 and 2 at 100.00" in verdict.reason
    assert "levels 3, 4 and 5 at 100.05" in verdict.reason
    assert "fewer grids" in verdict.reason


def test_levels_that_stay_distinct_are_not_refused() -> None:
    verdict = _find(_verdicts("0.01"))

    assert verdict is not None
    assert verdict.severity is VerdictSeverity.OK


def test_the_report_example_has_distinct_levels() -> None:
    verdicts = evaluate_grid(inputs(), GridThresholds()).verdicts

    verdict = _find(verdicts)
    assert verdict is not None and verdict.severity is VerdictSeverity.OK
