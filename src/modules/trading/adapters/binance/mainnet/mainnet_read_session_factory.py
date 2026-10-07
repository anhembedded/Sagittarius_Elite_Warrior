"""`EPIC-034E` — the one place that opens a signed session on Binance mainnet,
and it hands back the reading half only.

@details Mirrors `SpotSessionFactory`'s construction (a timeout, a
clock-corrected timestamp offset) with `testnet=False`. python-binance's
`Client` has order methods; the `cast` to `IMainnetReadClient` is what keeps
them out of reach of every caller, and
`test_mainnet_has_no_order_path.py` keeps this module away from
the trading venues' session factories.

Verification note: written from python-binance's own source and Binance's
documented API; egress to `*.binance.com` is blocked in this sandbox (HTTP 451),
so it was exercised against the fake Binance server only. The owner's own key
is the live check.
"""

from __future__ import annotations

import time
from typing import cast

from binance.client import Client
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    REQUEST_TIMEOUT_SECONDS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_mainnet_read_client import (
    IMainnetReadClient,
    IMainnetReadSessionFactory,
)


class MainnetReadSessionFactory(IMainnetReadSessionFactory):
    def create_read_client(
        self, credentials: ExchangeCredentials
    ) -> IMainnetReadClient:
        client = Client(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
            testnet=False,
        )
        before_ms = int(time.time() * 1000)
        server_ms = int(client.get_server_time()["serverTime"])
        after_ms = int(time.time() * 1000)
        client.timestamp_offset = server_ms - (before_ms + after_ms) // 2
        return cast(IMainnetReadClient, client)
