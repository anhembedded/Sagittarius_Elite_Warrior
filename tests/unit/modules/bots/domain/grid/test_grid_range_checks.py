"""`EPIC-044`, ADR 044 D6 (superseding `EPIC-035L` D4 (a)) - Start with the price outside the range.

A Grid started away from its range starts and waits for the price; the two range verdicts are
information for every direction alike, never a warning and never a refusal, and the words describe
no trade (the old ones said "would buy ... at market" and "BUY orders only", false for a SHORT).
The rest of the plan is judged where the bot will enter, at the nearest bound. D2 holds: the bot
grows no stop-loss warning and no stop-loss default.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
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
    inputs,
)

_BELOW, _ABOVE, _IN = "PRICE_BELOW_RANGE", "PRICE_ABOVE_RANGE", "PRICE_IN_RANGE"
#: The report's range is 60 000-70 000 with a 10 000 USDT capital.
_LOWER, _UPPER = Decimal(60000), Decimal(70000)
_POSITION_VENUE = ExposureLimits(frozenset(TradeDirection), 10, ExposureKind.POSITION)
_DIRECTIONS = ["LONG", "SHORT", "NEUTRAL"]


def _verdicts(
    price: Decimal, direction: str = "LONG", **changes: str
) -> tuple[Verdict, ...]:
    given = replace(
        inputs(last_price=price, direction=direction, leverage="1", **changes),
        limits=_POSITION_VENUE,
    )
    return evaluate_grid(given, GridThresholds()).verdicts


def _find(verdicts: tuple[Verdict, ...], code: str) -> Verdict | None:
    return next((v for v in verdicts if v.code == code), None)


@pytest.mark.parametrize("direction", _DIRECTIONS)
@pytest.mark.parametrize(
    ("price", "code"), [(Decimal(59000), _BELOW), (Decimal(71000), _ABOVE)]
)
def test_a_price_outside_the_range_is_information_for_every_direction(
    direction: str, price: Decimal, code: str
) -> None:
    verdicts = _verdicts(price, direction)

    told = _find(verdicts, code)
    assert told is not None
    assert told.severity is VerdictSeverity.OK
    assert not any(v.severity is VerdictSeverity.REFUSED for v in verdicts)
    assert told.numbers["last_price"] == price, "the real price, not the plan's"


@pytest.mark.parametrize("direction", _DIRECTIONS)
def test_the_words_say_the_bot_waits_and_describe_no_trade(direction: str) -> None:
    below = _find(_verdicts(Decimal(59000), direction), _BELOW)
    above = _find(_verdicts(Decimal(71000), direction), _ABOVE)

    assert below is not None and above is not None
    for told, price in ((below, "59000"), (above, "71000")):
        assert "Starts waiting for the price to enter 60000-70000" in told.reason
        assert f"(now {price})" in told.reason
        assert "nothing is placed until it does" in told.reason
        assert "BUY" not in told.reason
        assert "at market" not in told.reason


@pytest.mark.parametrize("price", [_LOWER, _UPPER, Decimal(65000)])
def test_a_price_on_a_bound_or_inside_has_neither_verdict(price: Decimal) -> None:
    verdicts = _verdicts(price)

    assert _find(verdicts, _BELOW) is None
    assert _find(verdicts, _ABOVE) is None
    assert _find(verdicts, _IN) is not None


@pytest.mark.parametrize(
    ("price", "edge"), [(Decimal(59000), _LOWER), (Decimal(71000), _UPPER)]
)
def test_the_verdict_names_the_bound_the_bot_will_enter_at(
    price: Decimal, edge: Decimal
) -> None:
    told = next(v for v in _verdicts(price) if v.code in (_BELOW, _ABOVE))

    assert told.numbers["entry_edge"] == edge


@pytest.mark.parametrize("direction", _DIRECTIONS)
def test_the_plan_is_judged_at_the_bound_not_at_a_price_the_bot_will_not_trade_at(
    direction: str,
) -> None:
    """The old SHORT-above case: judged at 71 000 the plan market-shorts 0.15 BTC while the bot
    will in fact enter at 70 000 or below."""
    outside = evaluate_grid(
        replace(
            inputs(last_price=Decimal(71000), direction=direction, leverage="1"),
            limits=_POSITION_VENUE,
        ),
        GridThresholds(),
    )
    at_the_bound = evaluate_grid(
        replace(
            inputs(last_price=_UPPER, direction=direction, leverage="1"),
            limits=_POSITION_VENUE,
        ),
        GridThresholds(),
    )

    assert outside.plan is not None and at_the_bound.plan is not None
    assert outside.plan.last_price == _UPPER
    assert outside.plan.opening_quantity == at_the_bound.plan.opening_quantity


def test_no_stop_loss_warning_and_no_default_stop_loss() -> None:
    """D2: a bot without a stop loss is judged exactly as before."""
    verdicts = _verdicts(Decimal(65000), stop_loss="off")

    off = _find(verdicts, "STOP_LOSS_OFF")
    assert off is not None and off.severity is VerdictSeverity.OK
    assert not [v for v in verdicts if v.code.startswith("STOP_LOSS") and v is not off]


def test_an_exit_refusal_prints_plain_prices() -> None:
    verdicts = _verdicts(
        Decimal(65000),
        stop_loss="price:61000.00000000",
        take_profit="price:69000.00000000",
    )

    stop = _find(verdicts, "STOP_LOSS_INSIDE_RANGE")
    take = _find(verdicts, "TAKE_PROFIT_INSIDE_RANGE")
    assert stop is not None and take is not None
    assert "stop loss 61000 is at or above the lower limit 60000;" in stop.reason
    assert "take profit 69000 is at or below the upper limit 70000;" in take.reason
