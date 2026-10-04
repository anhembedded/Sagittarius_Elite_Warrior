"""`EPIC-029H` — the gated Spot Testnet tests' boot, proven on the fake exchange.

`tests/testnet/` runs only on a person's machine with real keys, so a wiring
mistake in its fixtures used to surface first in that person's run: the grid
round trip's fixture asked `IVenueTradingPorts` for a `client_factory` it
does not publish and errored at setup. `composed_on_spot_testnet` is now the
one composition those tests share; this file runs it here, from the same
shipped config, against the fake Binance server, and reaches the trading
client and the planner market the round trip starts from. Turning trading
on is left to the person's run: it starts the user-data websocket, which the
fake server does not speak.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.tests.testnet.grid_testnet_app import (
    SPOT,
    SYMBOL,
    composed_on_spot_testnet,
    spot_testnet_config,
)

from .grid_fake_exchange import FakeExchange


def test_the_testnet_composition_reaches_the_client_and_the_market(
    exchange: FakeExchange, tmp_path: Path
) -> None:
    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        assert app.tagged_open("no-such-bot") == {}
        market = app.engine.dispatch(
            GetPlannerMarketQuery, GetPlannerMarketQuery(SPOT, SYMBOL)
        )
        assert isinstance(market, PlannerMarket)
        assert market.terms is not None, market.problem
