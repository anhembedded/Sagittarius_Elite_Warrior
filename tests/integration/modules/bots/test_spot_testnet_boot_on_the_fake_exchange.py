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

from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
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


def test_the_connect_step_reads_the_account_through_the_composed_app(
    exchange: FakeExchange, tmp_path: Path
) -> None:
    """`EPIC-034D` — one query returns what a design needs, read by the real
    Spot adapters: the balance, the fee, the key's flag, the filters, the price."""
    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        answer = app.engine.dispatch(
            GetVenueConnectionQuery, GetVenueConnectionQuery(SPOT, SYMBOL)
        )

        assert isinstance(answer, VenueAccountSnapshot), answer
        assert answer.source is AccountSource.SPOT_TESTNET
        assert answer.available > 0
        assert answer.can_trade is True
        assert answer.commission.taker == Decimal("0.001")
        assert answer.rules.symbol == SYMBOL
        assert answer.price > 0
        assert ("POST", "/api/v3/order") not in exchange.urls.requests
        assert not [r for r in exchange.urls.requests if "order" in r[1].lower()]


def test_a_maintenance_page_is_named_not_left_unclassified(
    exchange: FakeExchange, tmp_path: Path
) -> None:
    """`EPIC-034D` — the owner's 2026-10-07 Spot Testnet run: an HTML answer."""
    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        exchange.urls.maintenance.on = True

        answer = app.engine.dispatch(
            GetVenueConnectionQuery, GetVenueConnectionQuery(SPOT, SYMBOL)
        )

        assert isinstance(answer, ConnectFailure), answer
        assert answer.kind is ConnectionFailureKind.MAINTENANCE
