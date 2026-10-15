"""`BUG-210` — every Grid advice says the real number with its unit, the recommended value
in quote terms, what it means in plain words and what to do.

The owner met "The range is 4.72 daily ATRs wide, outside 2–4" under both price fields and
could not act on it: no width in USDT, no ATR value, no recommendation, "ATR" unexplained.
Each test here reads the numbers out of the plan and checks the sentence carries them; the
last ones follow the advice and check the plan then passes.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice import (
    ADVICE_TAIL,
)
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
    TERMS,
    inputs,
)

_THINNING = {
    "terms": replace(TERMS, max_open_orders=1000),
    "last_price": Decimal(150),
    "lower": "100",
    "upper": "200",
    "grid_count": "400",
    "capital_quote": "400000",
    "stop_loss": "off",
    "take_profit": "off",
}

#: One plan that provokes each piece of advice `grid_checks.py` words.
_ADVICE: dict[str, dict[str, object]] = {
    "RANGE_OUTSIDE_ATR_BAND": {"daily_atr": Decimal(1000)},
    "STEP_BELOW_MINIMUM": {"grid_count": "100", "capital_quote": "10000"},
    "SOME_GRIDS_LOSE": _THINNING,
    "FOREIGN_OPEN_ORDERS": {"foreign_open_orders": 3},
    "ARITHMETIC_ON_WIDE_RANGE": {
        "upper": "90000",
        "terms": replace(TERMS, max_notional_per_order=Decimal(10**6)),
    },
    "STOP_LOSS_DISTANCE": {"stop_loss": "percent:10"},
    "TAKE_PROFIT_DISTANCE": {"take_profit": "percent:10"},
}


def _verdicts(**kwargs: object) -> tuple[Verdict, ...]:
    return evaluate_grid(inputs(**kwargs), GridThresholds()).verdicts


def _verdict(code: str, **kwargs: object) -> Verdict:
    found = [v for v in _verdicts(**kwargs) if v.code == code]
    assert len(found) == 1, [v.code for v in _verdicts(**kwargs)]
    return found[0]


def _codes(**kwargs: object) -> set[str]:
    return {v.code for v in _verdicts(**kwargs)}


@pytest.mark.parametrize("code", sorted(_ADVICE))
def test_every_advice_names_the_money_in_its_unit_and_says_it_is_advice(
    code: str,
) -> None:
    verdict = _verdict(code, **_ADVICE[code])
    assert verdict.severity is VerdictSeverity.WARNING
    assert "USDT" in verdict.reason or code == "FOREIGN_OPEN_ORDERS"
    assert verdict.reason.endswith(ADVICE_TAIL)


# --- the owner's case: the range against the daily ATR -----------------------


def test_a_wide_range_names_its_width_the_atr_the_band_and_a_range_to_try() -> None:
    verdict = _verdict("RANGE_OUTSIDE_ATR_BAND", daily_atr=Decimal(1000))
    text = verdict.reason
    assert "Wide range: 10000 USDT" in text
    assert "BTC usually moves about 1000 USDT a day" in text
    assert "daily ATR" in text
    assert "average true range" in text  # the term is defined where it first appears
    assert "2000–4000 USDT" in text  # 2 and 4 days of the ATR, in money
    assert "63500–66500" in text  # the same middle, three ATRs wide
    assert "Suggest from ATR" in text
    assert "fills less often" in text


def test_a_narrow_range_says_what_a_narrow_range_costs() -> None:
    text = _verdict("RANGE_OUTSIDE_ATR_BAND", daily_atr=Decimal(10000)).reason
    assert "Narrow range: 10000 USDT" in text
    assert "leaves it sooner" in text
    assert "Suggest from ATR" in text


@pytest.mark.parametrize("atr", [Decimal(1000), Decimal(10000)])
def test_the_range_the_advice_proposes_passes_the_same_check(atr: Decimal) -> None:
    verdict = _verdict("RANGE_OUTSIDE_ATR_BAND", daily_atr=atr)
    followed = _verdicts(
        daily_atr=atr,
        lower=str(verdict.numbers["suggested_lower"]),
        upper=str(verdict.numbers["suggested_upper"]),
    )
    assert "RANGE_ATR" in {v.code for v in followed}


# --- the step ---------------------------------------------------------------


def test_a_thin_step_names_its_size_in_money_and_the_grids_that_would_fix_it() -> None:
    verdict = _verdict("STEP_BELOW_MINIMUM", **_ADVICE["STEP_BELOW_MINIMUM"])
    text = verdict.reason
    assert "USDT" in text and "%" in text
    assert "slippage" in text.lower()
    grids = int(verdict.numbers["suggested_grids"])
    assert f"{grids} grids or fewer" in text
    followed = _codes(**{**_ADVICE["STEP_BELOW_MINIMUM"], "grid_count": str(grids)})
    assert "STEP_SIZE" in followed


def test_thin_grids_that_lose_name_how_many_and_the_grids_that_would_fix_it() -> None:
    verdict = _verdict("SOME_GRIDS_LOSE", **_THINNING)
    assert "of 400 grids" in verdict.reason
    assert "USDT" in verdict.reason
    grids = int(verdict.numbers["suggested_grids"])
    assert f"{grids} grids or fewer" in verdict.reason
    assert "BREAK_EVEN" in _codes(**{**_THINNING, "grid_count": str(grids)})


# --- the orders already open --------------------------------------------------


def test_foreign_orders_give_the_count_the_limit_and_the_grids_that_still_fit() -> None:
    verdict = _verdict("FOREIGN_OPEN_ORDERS", foreign_open_orders=95)
    text = verdict.reason
    assert "95 other orders" in text
    assert "105 open orders against a limit of 100" in text
    assert "4 grids" in text
    assert "cancel" in text.lower()


def test_foreign_orders_that_still_fit_say_how_much_room_is_left() -> None:
    text = _verdict("FOREIGN_OPEN_ORDERS", foreign_open_orders=3).reason
    assert "3 other orders" in text
    assert "13 open orders against a limit of 100" in text
    assert "87 more" in text


# --- the spacing ---------------------------------------------------------------


def test_arithmetic_spacing_on_a_wide_range_names_the_range_and_a_narrower_one() -> (
    None
):
    text = _verdict(
        "ARITHMETIC_ON_WIDE_RANGE", **_ADVICE["ARITHMETIC_ON_WIDE_RANGE"]
    ).reason
    assert "30000 USDT" in text  # the range, 60000–90000
    assert "Geometric" in text
    assert "60000–72000 USDT" in text  # a 20% range from the lower limit


# --- the exits ------------------------------------------------------------------


def test_a_stop_loss_too_far_names_its_price_the_gap_and_the_advised_prices() -> None:
    text = _verdict("STOP_LOSS_DISTANCE", stop_loss="percent:10").reason
    assert "54000 USDT" in text
    assert "10.00%" in text and "6000 USDT" in text
    assert "55200–58200 USDT" in text  # 8% and 3% below 60000
    assert "stop loss" in text


def test_a_take_profit_too_close_names_its_price_and_the_advised_prices() -> None:
    text = _verdict("TAKE_PROFIT_DISTANCE", take_profit="percent:1").reason
    assert "70700 USDT" in text
    assert "72100–75600 USDT" in text  # 3% and 8% above 70000
    assert "take profit" in text


# --- an asset the symbol does not name ------------------------------------------


def test_without_asset_names_the_sentence_does_not_invent_them() -> None:
    base = inputs(daily_atr=Decimal(1000))
    market = replace(base.market, base_asset="", quote_asset="")
    text = next(
        v
        for v in evaluate_grid(replace(base, market=market), GridThresholds()).verdicts
        if v.code == "RANGE_OUTSIDE_ATR_BAND"
    ).reason
    assert "USDT" not in text and "BTC" not in text
    assert "quote" in text
