"""`BUG-146` — a level outside the price band Binance accepts is refused.

@details Binance Spot's `PERCENT_PRICE_BY_SIDE` filter accepts a BUY only
between `bidMultiplierDown` and `bidMultiplierUp` times the symbol's average
price, and a SELL between the `ask` pair. A Grid with a level outside that
band passed every check, and its Start faulted on the first rejected order:
`L10 BUY @ 2222 -> Filter failure: PERCENT_PRICE_BY_SIDE`, `STARTING -> ERROR`.
The check refuses such a plan before Start, at the current price.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PriceBand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    GridEvaluation,
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
    inputs,
)

_LAST = Decimal(65000)
#: Buys down to 0.8 × 65 000 = 52 000, sells up to 1.2 × 65 000 = 78 000.
_BAND = PriceBand(
    buy_down=Decimal("0.8"),
    buy_up=Decimal("1.2"),
    sell_down=Decimal("0.8"),
    sell_up=Decimal("1.2"),
)
_CODES = ("LEVEL_OUTSIDE_PRICE_BAND", "PRICE_BAND", "PRICE_BAND_NOT_PUBLISHED")


def _band_verdict(band: PriceBand | None, lower: str, upper: str) -> Verdict:
    evaluation: GridEvaluation = evaluate_grid(
        inputs(
            terms=replace(TERMS, price_band=band),
            last_price=_LAST,
            lower=lower,
            upper=upper,
            grid_count="4",
            stop_loss="off",
            take_profit="off",
        ),
        GridThresholds(),
    )
    matches = [v for v in evaluation.verdicts if v.code in _CODES]
    assert len(matches) == 1, evaluation.verdicts
    return matches[0]


def test_a_buy_level_below_the_band_refuses_and_names_it() -> None:
    verdict = _band_verdict(_BAND, lower="50000", upper="70000")

    assert verdict.code == "LEVEL_OUTSIDE_PRICE_BAND"
    assert verdict.refuses
    assert "50000" in verdict.reason and "52000" in verdict.reason
    assert verdict.numbers["lowest_buy_allowed"] == Decimal("52000.0")


def test_a_buy_level_exactly_at_the_band_passes() -> None:
    verdict = _band_verdict(_BAND, lower="52000", upper="70000")

    assert verdict.code == "PRICE_BAND"
    assert not verdict.refuses


def test_a_sell_level_above_the_band_refuses() -> None:
    verdict = _band_verdict(_BAND, lower="60000", upper="80000")

    assert verdict.code == "LEVEL_OUTSIDE_PRICE_BAND"
    assert "80000" in verdict.reason and "78000" in verdict.reason


def test_a_venue_without_a_band_says_the_check_did_not_run() -> None:
    verdict = _band_verdict(None, lower="50000", upper="70000")

    assert verdict.code == "PRICE_BAND_NOT_PUBLISHED"
    assert not verdict.refuses
