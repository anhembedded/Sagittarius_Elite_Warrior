"""`EPIC-039H` - the position model (`grid_position_model.py`, `EPIC-039B`) agrees with the executor.

@details The model is a model, not a replay (its own docstring). The Futures backtest (`EPIC-039K`)
rests on it, so this is the check that it says what the live executor does: the same ladder, the
same price path, one price at a time. After every price the signed position the exchange holds,
the one the bot counted from its own fills and the one the model derives are the same, and so are
the profit the model books and the one the executor's cycles book (no fees on the fake's quote
side beyond the commission, which the comparison allows for).

The fake's delivery is not re-entrant, so each price of the path crosses one resting order.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.bot_exchange_terms import (
    exchange_terms_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    model_position_along,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)

from .futures_bots_world import booted_futures_bots
from .futures_direction_scenarios import SCENARIOS, DirectionScenario
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import _started

D = Decimal
S = BotLifecycleState


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.direction.name)
def test_the_model_and_the_executor_hold_the_same_position_after_every_price(
    futures: FakeExchange, scenario: DirectionScenario
) -> None:
    """Each price of the path crosses one order of the ladder (a fill, its counter, the next...)."""
    with booted_futures_bots(futures) as app:
        bot_id = _started(app, scenario.config)
        container = app.engine.context.container
        ports = container.resolve(IVenueTradingPorts).get(FUTURES)
        terms = exchange_terms_for(
            ports.order_entry_terms, SYMBOL, container.resolve(OwnerBudgetCaps)
        )
        planned = plan(
            GridParams.from_config(scenario.config),
            terms,
            D(64000),
            LevelSizing.EQUAL_QUANTITY,
        )
        assert planned.opening_quantity == scenario.opening, "the same ladder"
        # The model prices the opening at the plan's last price; the fake fills the market order
        # at the ask (a BUY) or the bid (a SELL), one tick away from it.
        opening_slippage = abs(scenario.opening) * terms.tick_size

        for step, price in enumerate(scenario.model_path, start=1):
            app.move_price(price)
            modelled = model_position_along(planned, scenario.model_path[:step])

            assert app.bot(bot_id).state is S.RUNNING
            assert app.position() == modelled.position, f"exchange at {price}"
            runtime = app.runtime(bot_id)
            assert runtime.inventory == modelled.position, f"bot count at {price}"
            assert abs(runtime.realised_total - modelled.realised) <= (
                runtime.commissions + opening_slippage
            ), (
                f"profit at {price}: the executor books {runtime.realised_total}, the "
                f"model {modelled.realised}, the commissions were {runtime.commissions}"
            )
