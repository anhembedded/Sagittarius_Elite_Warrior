"""`EPIC-035V` (L7) — orders already open on the symbol are advice, counted against the limit."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    GridEvaluation,
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
    TERMS,
    inputs,
)

OK = VerdictSeverity.OK
WARNING = VerdictSeverity.WARNING


def _verdict(evaluation: GridEvaluation, *codes: str) -> Verdict:
    matches = [v for v in evaluation.verdicts if v.code in codes]
    assert len(matches) == 1, evaluation.verdicts
    return matches[0]


def _evaluate(**kwargs: object) -> GridEvaluation:
    return evaluate_grid(inputs(**kwargs), GridThresholds())


# --- orders already open on the symbol (L7, `EPIC-035V`) -------------------


def test_orders_already_open_on_the_symbol_warn_and_count_against_the_limit() -> None:
    evaluation = _evaluate(foreign_open_orders=3)
    verdict = _verdict(evaluation, "FOREIGN_OPEN_ORDERS", "NO_FOREIGN_ORDERS")
    assert verdict.code == "FOREIGN_OPEN_ORDERS"
    assert verdict.severity is WARNING
    assert verdict.numbers["foreign"] == Decimal(3)
    assert verdict.numbers["total"] == verdict.numbers["orders"] + Decimal(3)
    assert verdict.numbers["max_open_orders"] == Decimal(TERMS.max_open_orders)
    assert "3 other" in verdict.reason


def test_no_foreign_order_is_not_a_warning() -> None:
    verdict = _verdict(
        _evaluate(foreign_open_orders=0), "FOREIGN_OPEN_ORDERS", "NO_FOREIGN_ORDERS"
    )
    assert verdict.code == "NO_FOREIGN_ORDERS"
    assert verdict.severity is OK


def test_an_unread_count_says_the_check_did_not_run() -> None:
    verdict = _verdict(
        _evaluate(foreign_open_orders=None),
        "FOREIGN_OPEN_ORDERS",
        "NO_FOREIGN_ORDERS",
        "FOREIGN_ORDERS_NOT_READ",
    )
    assert verdict.code == "FOREIGN_ORDERS_NOT_READ"
    assert verdict.severity is OK
