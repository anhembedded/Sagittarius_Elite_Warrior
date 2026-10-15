"""`EPIC-039I` (after `BUG-212`) - the Plan's order checks and the orders the executor sends agree.

@details A check that passed while the executor sent an order the exchange refuses is the incident
of 2026-10-15 (Spot). A position ladder gives every order one quantity, but any rung can hold an
order sooner or later: a fill owes its counter at the neighbouring rung, so the rung left EMPTY at
start takes one too. These tests fill a ladder through the **real reaction code** (`on_fill`,
`on_end`) along seeded walks and hold every order it emits to the exchange's filters; a plan the
shared sizing (`grid_order_sizing`) accepts must never emit one that breaks them, and the
plan's verdicts and the executor's `find_breach` and `find_cap_breach` must say the same thing about the same plan.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from itertools import product

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    ladder_orders,
    runtime_from_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_order_sizing import (
    find_breach,
    find_cap_breach,
    smallest_order,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
    LevelEnd,
    LevelFill,
    PlaceOrder,
    Reaction,
    accepted,
    on_end,
    on_fill,
    placed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
    inputs,
)

D = Decimal
_AT = datetime(2026, 10, 15, tzinfo=UTC)
_LIMITS = ExposureLimits(
    frozenset({TradeDirection.LONG, TradeDirection.SHORT}), 125, ExposureKind.POSITION
)
_STEP = D("0.001")
#: Level 0 (62,000) is the cheapest rung. At a quantity of 0.006 it is worth 372; the next
#: rung up, 378. A minimum of 375 lies between them.
_RUNGS = {
    "lower": "62000",
    "upper": "66000",
    "grid_count": "4",
    "capital_quote": "528",
    "stop_loss": "off",
    "take_profit": "off",
    "leverage": "3",
}


def _terms(minimum: str) -> ExchangeTerms:
    return replace(
        TERMS,
        tick_size=D("0.1"),
        step_size=_STEP,
        min_notional=D(minimum),
        max_notional_per_order=D(500),
    )


def _kind_inputs(
    direction: str, last: str, minimum: str, **changes: str
) -> BotKindInputs:
    base = inputs(
        terms=_terms(minimum),
        last_price=D(last),
        **{**CONFIG, **_RUNGS, "direction": direction, **changes},
    )
    return BotKindInputs(base.config, base.terms, base.market, limits=_LIMITS)


def _plan(direction: str, last: str, minimum: str, **changes: str) -> GridPlan:
    evaluated = evaluate_grid(
        _kind_inputs(direction, last, minimum, **changes), GridThresholds()
    )
    assert evaluated.plan is not None
    return evaluated.plan


def _breach(ladder: GridPlan, direction: str, last: str, minimum: str) -> object | None:
    """What the executor's opening asks of the one sizing module before it sends anything."""
    params = GridParams.from_config(_kind_inputs(direction, last, minimum).config)
    terms = _terms(minimum)
    return find_breach(params, ladder, terms) or find_cap_breach(ladder, terms)


def _refused_codes(direction: str, last: str, minimum: str, **changes: str) -> set[str]:
    verdicts = evaluate_grid(
        _kind_inputs(direction, last, minimum, **changes), GridThresholds()
    ).verdicts
    return {v.code for v in verdicts if v.refuses}


def test_the_rung_left_empty_at_start_is_judged_like_any_other() -> None:
    """The red case: a price a hair above 62,000 leaves that rung EMPTY, and the first SELL to fill
    owes a BUY there, worth 372 against a minimum of 375. The old check read only the rungs that
    held an order (378) and passed."""
    ladder = _plan("LONG", "62010", "375")

    assert ladder.levels[0].side.value == "EMPTY"
    smallest = smallest_order(ladder, _terms("375"))
    assert smallest is not None and smallest.notional == D("372.000")
    assert smallest.level_index == 0
    assert "LEVEL_BELOW_MIN_NOTIONAL" in _refused_codes("LONG", "62010", "375")
    assert _breach(ladder, "LONG", "62010", "375") is not None


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_a_ladder_whose_every_rung_clears_the_minimum_is_not_refused(
    direction: str,
) -> None:
    assert "LEVEL_BELOW_MIN_NOTIONAL" not in _refused_codes(direction, "62010", "300")
    assert _breach(_plan(direction, "62010", "300"), direction, "62010", "300") is None


def _walk(ladder: GridPlan, terms: ExchangeTerms, seed: int) -> list[PlaceOrder]:
    """Every order the real reactions emit while a seeded walk fills the ladder: whole fills,
    and part fills whose remainder then ends."""
    rules = LadderRules(terms.step_size, terms.min_notional)
    runtime = runtime_from_plan(ladder, terms.step_size)
    rng = random.Random(seed)  # noqa: S311 - a seeded walk, not a secret
    sent: list[PlaceOrder] = []
    counter = 0

    def send(state: GridRuntime, action: PlaceOrder) -> GridRuntime:
        nonlocal counter
        counter += 1
        order_id = f"SEW-test-{counter:010d}"
        sent.append(action)
        return accepted(placed(state, action, order_id), order_id)

    for action in ladder_orders(ladder):
        runtime = send(runtime, action)
    for _ in range(60):
        resting = [lv for lv in runtime.levels if lv.order is not None]
        if not resting:
            break
        level = rng.choice(resting)
        order = level.order
        assert order is not None
        if rng.random() < 0.25 and order.quantity >= 2 * terms.step_size:
            part = (order.quantity / 2).quantize(terms.step_size)
            reaction = on_fill(
                runtime,
                LevelFill(order.client_order_id, order.price, part),
                terms.step_size,
                False,
            )
            runtime = _perform(reaction, send)
            ended = runtime.level_of(order.client_order_id)
            if ended is not None:
                reaction = on_end(
                    runtime, LevelEnd(order.client_order_id, _AT), rules, False
                )
                runtime = _perform(reaction, send)
            continue
        reaction = on_fill(
            runtime,
            LevelFill(order.client_order_id, order.price, order.quantity),
            terms.step_size,
            False,
        )
        runtime = _perform(reaction, send)
    return sent


def _perform(
    reaction: Reaction,
    send: "callable[[GridRuntime, PlaceOrder], GridRuntime]",  # noqa: UP037
) -> GridRuntime:
    runtime = reaction.runtime
    for action in reaction.actions:
        if isinstance(action, PlaceOrder):
            runtime = send(runtime, action)
    return runtime


_CASES = list(
    product(
        ("LONG", "SHORT"),
        ("62010", "63400", "64000", "65990"),
        ("5", "375", "378", "380"),
        (1, 2, 3),
    )
)


@pytest.mark.parametrize(("direction", "last", "minimum", "seed"), _CASES)
def test_a_plan_the_shared_sizing_accepts_never_makes_the_reactions_send_a_breaking_order(
    direction: str, last: str, minimum: str, seed: int
) -> None:
    ladder = _plan(direction, last, minimum)
    terms = _terms(minimum)
    refused = _refused_codes(direction, last, minimum)

    # The plan's verdicts and the executor's judgement are one decision.
    breach = _breach(ladder, direction, last, minimum)
    judged = {"LEVEL_BELOW_MIN_NOTIONAL", "LEVEL_ABOVE_MAX_NOTIONAL"} & refused
    assert bool(judged) == (breach is not None), (judged, breach)
    if breach is not None:
        return

    sent = _walk(ladder, terms, seed)

    assert sent, "the walk must send something to prove anything"
    for action in sent:
        assert action.quantity > 0
        assert action.quantity % terms.step_size == 0, action
        assert action.price * action.quantity >= terms.min_notional, action
        assert action.price * action.quantity <= terms.max_notional_per_order, action


def test_the_walk_does_send_a_breaking_order_when_the_sizing_is_not_consulted() -> None:
    """The walk can fail: over the plan the old check passed, it reaches the cheap rung."""
    ladder = _plan("LONG", "62010", "375")
    terms = _terms("375")
    assert _breach(ladder, "LONG", "62010", "375") is not None

    sent = [a for seed in range(1, 6) for a in _walk(ladder, terms, seed)]

    assert any(a.price * a.quantity < terms.min_notional for a in sent)
