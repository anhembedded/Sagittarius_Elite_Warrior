"""`EPIC-044D` (ADR 044 D11) - one price path, replayed and driven live, enters on the same step.

The live bot (`GridRangeEntry`, over the simulated venue) and the replay (`simulate_grid` over
1-second klines) are given the same closes, one per second, for a window that opens below the range
100-140. Each is asked which step it entered on: the first whose close is inside, the bound included,
and a step whose wick reaches the range but whose close stays outside enters on neither.

The Futures replay approximates the mark with the trade close (ADR 044 D11, stated limit): the
parity is of the trade-price path, which is what the live Spot bot is judged on and what the live
Futures bot's mark is fed here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.fine_klines import (
    FineKlinesByCandle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_replay import (
    FuturesReplay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.waiting_world import (
    WITH_NO_EXITS,
    a_wait,
    started,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    terms_of,
)

D = Decimal
START = datetime(2026, 10, 21, tzinfo=UTC)
TERMS = ExchangeTerms(
    tick_size=D("0.01"),
    step_size=D("0.0001"),
    min_notional=D(5),
    maker_fee=D("0.001"),
    taker_fee=D("0.001"),
    max_notional_per_order=D(5000),
    max_open_orders=100,
)

#: (closes, one wick per step) - the wick is the step's high; `None` is no wick.
_PATHS = {
    "a_plain_climb": ([95, 97, 99, 101, 104], {}),
    "the_bound_itself": ([95, 97, 99, "99.99", 100, 104], {}),
    "a_wick_into_the_range_that_closes_outside": (
        [95, 97, 99, 98, 101, 104],
        {2: 103, 3: 110},
    ),
}


def _entry_step_live(market: str, direction: str, closes: list[Decimal]) -> int | None:
    case = started(a_wait(market, direction, closes[0]))
    for index, close in enumerate(closes):
        case.price_is(close)
        if case.world.state() is BotLifecycleState.RUNNING:
            return index
    return None


def _klines(closes: list[Decimal], wicks: dict[int, int]) -> list[PriceBar]:
    klines, previous = [], closes[0]
    for index, close in enumerate(closes):
        top = max(previous, close, D(wicks.get(index, 0)))
        bottom = min(previous, close)
        klines.append(
            PriceBar(START + timedelta(seconds=index), previous, top, bottom, close)
        )
        previous = close
    return klines


def _entry_step_replay(
    market: str, direction: str, closes: list[Decimal], wicks: dict[int, int]
) -> int | None:
    config = {**WITH_NO_EXITS, "direction": direction, "leverage": "1"}
    params = GridParams.from_config(config if market == "futures" else WITH_NO_EXITS)
    fine = _klines(closes, wicks)
    bar = PriceBar(
        START,
        closes[0],
        max(k.high for k in fine),
        min(k.low for k in fine),
        closes[-1],
    )
    engine = (
        (lambda first: FuturesReplay(params, TERMS, terms_of(), first))
        if market == "futures"
        else None
    )
    result = simulate_grid(
        GridBacktestInputs(
            params,
            TERMS,
            (bar,),
            timedelta(minutes=1),
            FineKlinesByCandle({bar.time: tuple(fine)}),
            engine=engine,
        )
    )
    assert isinstance(result, GridBacktestResult)
    if result.range_entry is None:
        return None
    return int((result.range_entry.time - START).total_seconds())


@pytest.mark.parametrize("path", sorted(_PATHS))
@pytest.mark.parametrize(
    ("market", "direction"),
    [
        ("spot", "LONG"),
        ("futures", "LONG"),
        ("futures", "SHORT"),
        ("futures", "NEUTRAL"),
    ],
    ids=["spot-long", "futures-long", "futures-short", "futures-neutral"],
)
def test_the_replay_and_the_live_bot_enter_on_the_same_step(
    path: str, market: str, direction: str
) -> None:
    raw, wicks = _PATHS[path]
    closes = [D(str(price)) for price in raw]

    live = _entry_step_live(market, direction, closes)
    replayed = _entry_step_replay(market, direction, closes, wicks)

    assert live is not None, "the path does enter the range"
    assert replayed == live
