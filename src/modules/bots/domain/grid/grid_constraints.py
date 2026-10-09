"""`EPIC-034F` — every constraint on a Grid's plan, named, with its class (D7).

A constraint is one named assertion: a check that reads the plan, the venue's
terms and the account, and answers a `Verdict` carrying its numbers. This table
is the one list the screen, `GridKind.validate` and the readiness query
(`EPIC-034H`) all run, so a plan is judged the same wherever it is.

**Blocking or advisory (decision D7).** A constraint *blocks* Start when it
states the exchange's rules or money: the balance, the minimum notional, the
per-order cap, the open-order limit, the price band, break-even after fees, the
key's permission, an exit on the wrong side of the range, a price below the range
(`EPIC-035L`: the plan would market-buy the whole capital), levels that round to
one price (`EPIC-035S`). It *advises* for
strategy judgement: the ATR, the slippage room, the spacing, how far an exit is.
Each constraint lists the violation codes it can answer and, per code, whether
that violation blocks; a violation blocks exactly when its verdict is
`REFUSED`, which `tests/unit/modules/bots/domain/grid/test_grid_constraints.py`
holds by provoking every code. A check may block in one case and advise in
another (break-even: every grid loses is a refusal, some grids lose a warning).

A check that cannot run answers OK saying so; it never violates.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_account_checks import (
    check_key_may_trade,
    check_opening_buy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_checks import (
    check_break_even,
    check_foreign_orders,
    check_max_notional,
    check_min_notional,
    check_min_step,
    check_open_orders,
    check_price_band,
    check_range_against_atr,
    check_spacing_for_range,
    check_stop_loss,
    check_take_profit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_checks import (
    check_distinct_levels,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_range_checks import (
    check_price_against_range,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


@dataclass(frozen=True, slots=True)
class GridConstraint:
    """One named assertion on a Grid's plan."""

    name: str
    check: Callable[[GridCheckInputs], Verdict]
    #: Each code the check answers when the plan violates it, and whether that
    #: violation blocks Start (D7).
    violations: Mapping[str, bool]

    def __post_init__(self) -> None:
        object.__setattr__(self, "violations", MappingProxyType(dict(self.violations)))

    @property
    def can_block(self) -> bool:
        return any(self.violations.values())


GRID_CONSTRAINTS: tuple[GridConstraint, ...] = (
    GridConstraint(
        "break_even_after_fees",
        check_break_even,
        {"EVERY_CYCLE_LOSES": True, "SOME_GRIDS_LOSE": False},
    ),
    GridConstraint(
        "order_above_exchange_minimum",
        check_min_notional,
        {"LEVEL_BELOW_MIN_NOTIONAL": True},
    ),
    GridConstraint(
        "order_within_per_order_cap",
        check_max_notional,
        {"LEVEL_ABOVE_MAX_NOTIONAL": True},
    ),
    GridConstraint(
        "orders_within_open_limit", check_open_orders, {"TOO_MANY_LEVELS": True}
    ),
    GridConstraint(
        "symbol_has_no_foreign_orders",
        check_foreign_orders,
        {"FOREIGN_OPEN_ORDERS": False},
    ),
    GridConstraint(
        "levels_inside_price_band", check_price_band, {"LEVEL_OUTSIDE_PRICE_BAND": True}
    ),
    GridConstraint(
        "price_suits_the_range",
        check_price_against_range,
        {"PRICE_BELOW_RANGE": True, "PRICE_ABOVE_RANGE": False},
    ),
    GridConstraint(
        "every_level_has_its_own_price",
        check_distinct_levels,
        {"LEVELS_ROUND_TO_ONE_PRICE": True},
    ),
    GridConstraint("opening_buy_is_planned", check_opening_buy, {}),
    GridConstraint("key_may_trade", check_key_may_trade, {"KEY_CANNOT_TRADE": True}),
    GridConstraint(
        "step_leaves_slippage_room", check_min_step, {"STEP_BELOW_MINIMUM": False}
    ),
    GridConstraint(
        "range_matches_volatility",
        check_range_against_atr,
        {"RANGE_OUTSIDE_ATR_BAND": False},
    ),
    GridConstraint(
        "stop_loss_is_sound",
        check_stop_loss,
        {"STOP_LOSS_INSIDE_RANGE": True, "STOP_LOSS_DISTANCE": False},
    ),
    GridConstraint(
        "take_profit_is_sound",
        check_take_profit,
        {"TAKE_PROFIT_INSIDE_RANGE": True, "TAKE_PROFIT_DISTANCE": False},
    ),
    GridConstraint(
        "spacing_suits_range",
        check_spacing_for_range,
        {"ARITHMETIC_ON_WIDE_RANGE": False},
    ),
)


def run_checks(inputs: GridCheckInputs) -> tuple[Verdict, ...]:
    """One verdict per constraint, in the table's order."""
    return tuple(constraint.check(inputs) for constraint in GRID_CONSTRAINTS)
