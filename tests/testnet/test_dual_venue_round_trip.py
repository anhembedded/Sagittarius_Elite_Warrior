"""`EPIC-028N` — one process trades both desks' venues on the real Testnets.

`test_order_lifecycle.py` and `spot/test_spot_order_lifecycle.py` each prove
one venue with adapters built by hand. This test proves what the two desks
rely on: the composition root, configured with both venues, hands each venue
its own adapters and credentials through `IVenueContexts`, and both work in
the same process. A Futures position is opened and closed, and a Spot asset
is bought and sold, each back to its baseline (`round_trips.py`).

Opt-in only, behind the same two gates as the rest of this tree
(`conftest.py`). It needs both key pairs, and skips naming the one that is
missing. The app reads the keys itself, from the environment first and then
`src/config/secrets.local.json`, the same sources the fixtures check.

The app is built but not booted. `create_app()` already binds every venue's
ports, and booting would start the market streams and user-data websockets,
which this test does not need.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.testnet.round_trips import (
    futures_open_and_close,
    spot_buy_and_sell,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "src" / "config"
_VENUES = (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET)


@pytest.fixture
def venue_contexts(
    testnet_credentials: object, spot_testnet_credentials: object, tmp_path: Path
) -> Iterator[IVenueContexts]:
    """The composed app's venue registry with both Testnets enabled. The two
    credential fixtures are the gates; the app resolves the keys itself."""
    user_json = tmp_path / "user_config.json"
    user_json.write_text(json.dumps({}))
    config = ConfigManager()
    config.load_json(str(_CONFIG_DIR / "app_config.json"))
    config.load_json(str(user_json), writable=True)
    config.load_dict({"exchange.trading_venues": [venue.value for venue in _VENUES]})
    app = create_app(config)
    try:
        yield app.context.container.resolve(IVenueContexts)
    finally:
        app.stop()


def test_one_process_trades_both_venues_back_to_baseline(
    venue_contexts: IVenueContexts,
) -> None:
    assert venue_contexts.enabled() == _VENUES
    futures = venue_contexts.get(TradingVenue.FUTURES_TESTNET)
    spot = venue_contexts.get(TradingVenue.SPOT_TESTNET)
    assert (futures.venue, spot.venue) == _VENUES

    futures_open_and_close(futures.client_factory.create(OrderSubmissionMode.LIVE))
    spot_buy_and_sell(
        spot.client_factory.create(OrderSubmissionMode.LIVE),
        spot.account_reader,
        spot.metadata_provider,
    )
