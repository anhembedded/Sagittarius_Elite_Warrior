"""`EPIC-027A` acceptance criterion: on the mainnet public venue, Spot
candles come from `/api/v3/klines` and USDⓈ-M candles from
`/fapi/v1/klines` — one `PythonBinanceClient`, built once against the
mainnet-public venue, must route each call to the right host family from
the `MarketType` argument alone, never from how it was constructed.

@details Not a unit test: this drives a real `binance.client.Client`
through `MarketDataSessionFactory` and a real HTTP round trip to the fake
server, same reasoning as `test_session_factories_against_fake_server.py`.
`Client.API_URL` and `Client.FUTURES_URL` are BOTH patched to the one fake
server's two path prefixes — mirroring real mainnet, where a single
`Client(testnet=False)` instance always knows both `api.binance.com` and
`fapi.binance.com` at once (`_create_futures_api_uri` reads `FUTURES_URL`
whenever `testnet` is `False`, regardless of which host spot calls use).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.market_data_session_factory import (
    MarketDataSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server


def test_spot_and_futures_klines_hit_their_own_endpoint_on_the_same_client():
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_URL", urls.spot),
        patch.object(Client, "FUTURES_URL", urls.futures),
    ):
        client = MarketDataSessionFactory(
            MarketDataVenue.MAINNET_PUBLIC
        ).create_market_data_client()

        spot_klines = client.get_historical_klines(
            MarketType.SPOT, "BTCUSDT", TimeFrame.ONE_MINUTE, "1 day ago UTC"
        )
        futures_klines = client.get_historical_klines(
            MarketType.FUTURES_USD_M, "BTCUSDT", TimeFrame.ONE_MINUTE, "1 day ago UTC"
        )

        # Each route's fixed fake row is distinguishable by open_price
        # (fake_exchange/spot_routes.py's 111.0 vs futures_routes.py's
        # 222.0) — content proves which path actually answered.
        assert len(spot_klines) == 1
        assert spot_klines[0].open_price == 111.0
        assert len(futures_klines) == 1
        assert futures_klines[0].open_price == 222.0
