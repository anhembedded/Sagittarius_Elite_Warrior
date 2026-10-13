"""`EPIC-039B` - the Spot corpus: the inputs the oracle replays, built from a fixed seed.

Only inputs live here. What the current planner and simulator returned for them was recorded
once, before `039B` changed anything, into `spot_oracle.json` by `record.py`; the test in
`test_the_spot_oracle.py` replays these inputs on today's code and compares. The inputs must
not change (a new case is a new seed range, recorded afresh), or the file stops being the
proof.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import cache

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
)

PLAN_CASES = 600
SIMULATION_CASES = 80
_START = datetime(2026, 9, 1, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
_TICKS = (Decimal("0.01"), Decimal("0.1"), Decimal(1))
_STEPS = (Decimal("0.00001"), Decimal("0.001"), Decimal("0.1"))


@dataclass(frozen=True)
class PlanCase:
    config: dict[str, str]
    terms: ExchangeTerms
    last_price: Decimal


@dataclass(frozen=True)
class SimulationCase:
    config: dict[str, str]
    terms: ExchangeTerms
    bars: tuple[PriceBar, ...]


def _money(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")


def _terms(rng: random.Random) -> ExchangeTerms:
    return ExchangeTerms(
        tick_size=_TICKS[int(rng.random() * len(_TICKS))],
        step_size=_STEPS[int(rng.random() * len(_STEPS))],
        min_notional=Decimal(5),
        maker_fee=Decimal("0.001"),
        taker_fee=Decimal("0.001") if rng.random() < 0.5 else Decimal("0.00075"),
        max_notional_per_order=Decimal(5000),
        max_open_orders=100,
    )


def _config(rng: random.Random) -> dict[str, str]:
    lower = _money(100 + rng.random() * 900)
    upper = _money(float(lower) * (1.05 + rng.random() * 0.9))
    spacing = "ARITHMETIC" if rng.random() < 0.5 else "GEOMETRIC"
    stop = "off" if rng.random() < 0.5 else f"percent:{1 + int(rng.random() * 9)}"
    take = "off" if rng.random() < 0.5 else f"percent:{1 + int(rng.random() * 9)}"
    return {
        "lower": str(lower),
        "upper": str(upper),
        "grid_count": str(1 + int(rng.random() * 30)),
        "spacing": spacing,
        "capital_quote": str(_money(100 + rng.random() * 9900)),
        "stop_loss": stop,
        "take_profit": take,
    }


@cache
def plan_cases() -> tuple[PlanCase, ...]:
    """600 plans: the price inside, on an edge and outside the range, both spacings."""
    cases: list[PlanCase] = []
    for seed in range(PLAN_CASES):
        rng = random.Random(seed)  # noqa: S311 - a seeded test generator, not a secret
        config = _config(rng)
        lower, upper = Decimal(config["lower"]), Decimal(config["upper"])
        where = rng.random()
        if where < 0.1:
            price = lower * Decimal("0.8")
        elif where < 0.2:
            price = upper * Decimal("1.2")
        elif where < 0.25:
            price = lower
        elif where < 0.3:
            price = upper
        else:
            price = lower + (upper - lower) * _money(rng.random())
        cases.append(PlanCase(config, _terms(rng), _round(price)))
    return tuple(cases)


def _round(price: Decimal) -> Decimal:
    return price.quantize(Decimal("0.01"))


@cache
def simulation_cases() -> tuple[SimulationCase, ...]:
    """80 random walks of 40-120 one-minute candles, many crossing the whole range."""
    cases: list[SimulationCase] = []
    for seed in range(10_000, 10_000 + SIMULATION_CASES):
        rng = random.Random(seed)  # noqa: S311 - a seeded test generator, not a secret
        config = _config(rng)
        lower, upper = Decimal(config["lower"]), Decimal(config["upper"])
        price = lower + (upper - lower) * _money(rng.random())
        swing = (upper - lower) * Decimal("0.12")
        bars: list[PriceBar] = []
        for minute in range(40 + int(rng.random() * 80)):
            move = (_money(rng.random()) - Decimal("0.5")) * swing
            close = max(_round(price + move), Decimal("0.01"))
            high = _round(max(price, close) + _money(rng.random()) * swing / 4)
            low = max(
                _round(min(price, close) - _money(rng.random()) * swing / 4),
                Decimal("0.01"),
            )
            bars.append(
                PriceBar(_START + minute * MINUTE, _round(price), high, low, close)
            )
            price = close
        cases.append(SimulationCase(config, _terms(rng), tuple(bars)))
    return tuple(cases)
