"""`EPIC-035L`, owner decision D4 (a) — Start with the price outside the range.

Below the lower bound every level is a SELL level, so the plan would market-buy
the whole capital's base before laying one order: REFUSED. Above the upper bound
every level is a BUY level, nothing is bought and the bot waits for a fall: a
WARNING, Start allowed. Inside the range, and exactly on either bound, neither.
D2 holds: the bot grows no stop-loss warning and no stop-loss default.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
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

_BELOW, _ABOVE = "PRICE_BELOW_RANGE", "PRICE_ABOVE_RANGE"
#: The report's range is 60 000–70 000 with a 10 000 USDT capital.
_LOWER, _UPPER = Decimal(60000), Decimal(70000)


def _verdicts(price: Decimal, **changes: str) -> tuple[Verdict, ...]:
    return evaluate_grid(inputs(last_price=price, **changes), GridThresholds()).verdicts


def _find(verdicts: tuple[Verdict, ...], code: str) -> Verdict | None:
    return next((v for v in verdicts if v.code == code), None)


def test_a_price_below_the_lower_bound_is_refused() -> None:
    refusal = _find(_verdicts(Decimal(59000)), _BELOW)

    assert refusal is not None
    assert refusal.severity is VerdictSeverity.REFUSED
    assert refusal.numbers["last_price"] == Decimal(59000)
    assert refusal.numbers["lower"] == _LOWER
    assert Decimal(9990) < refusal.numbers["opening_quote"] <= Decimal(10000)


def test_a_price_exactly_at_the_lower_bound_is_not_refused() -> None:
    assert _find(_verdicts(_LOWER), _BELOW) is None


def test_a_price_above_the_upper_bound_warns_and_does_not_refuse() -> None:
    verdicts = _verdicts(Decimal(71000))

    warning = _find(verdicts, _ABOVE)
    assert warning is not None
    assert warning.severity is VerdictSeverity.WARNING
    assert not any(v.severity is VerdictSeverity.REFUSED for v in verdicts)


def test_a_price_exactly_at_the_upper_bound_does_not_warn() -> None:
    assert _find(_verdicts(_UPPER), _ABOVE) is None


@pytest.mark.parametrize("price", [Decimal(60001), Decimal(65000), Decimal(69999)])
def test_a_price_inside_the_range_has_neither_verdict(price: Decimal) -> None:
    verdicts = _verdicts(price)

    assert _find(verdicts, _BELOW) is None
    assert _find(verdicts, _ABOVE) is None


def test_the_range_verdicts_name_the_figures_and_the_next_action() -> None:
    refusal = _find(_verdicts(Decimal(59000)), _BELOW)
    warning = _find(_verdicts(Decimal(71000)), _ABOVE)

    assert refusal is not None and warning is not None
    assert "59000" in refusal.reason and "60000" in refusal.reason
    assert "100% of the capital" in refusal.reason
    assert "Lower the range" in refusal.reason
    assert "71000" in warning.reason and "70000" in warning.reason
    assert "BUY orders only" in warning.reason


def test_below_the_range_blocks_start_and_above_it_nothing_does() -> None:
    below = {v.code for v in _verdicts(Decimal(59000)) if v.severity.name == "REFUSED"}
    above = {v.code for v in _verdicts(Decimal(71000)) if v.severity.name == "REFUSED"}

    assert _BELOW in below
    assert above == set()


def test_no_stop_loss_warning_and_no_default_stop_loss() -> None:
    """D2: a bot without a stop loss is judged exactly as before."""
    verdicts = _verdicts(Decimal(65000), stop_loss="off")

    off = _find(verdicts, "STOP_LOSS_OFF")
    assert off is not None and off.severity is VerdictSeverity.OK
    assert not [v for v in verdicts if v.code.startswith("STOP_LOSS") and v is not off]
