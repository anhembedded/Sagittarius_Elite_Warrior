"""`EPIC-027H` — the one place allowed to construct a signed
`binance.client.Client` for reading a Spot Testnet account, mirroring
`FuturesSessionFactory`'s own construction pattern (`testnet=True`,
`REQUEST_TIMEOUT_SECONDS`, a clock-skew-corrected `timestamp_offset`)
with Spot's own unprefixed session-client methods
(`ping`/`get_server_time`/`get_account`) in place of Futures' `futures_*`
ones.
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)


def _sync_timestamp_offset(client: Client) -> None:
    """Spot's own version of `FuturesSessionFactory`'s `BUG-111` fix: the
    same `Client.timestamp_offset` attribute is shared across both API
    families regardless of which one measures it, so this uses Spot's
    `get_server_time()` in place of Futures' `futures_time()`."""
    local_before_ms = int(time.time() * 1000)
    server_time_ms = int(client.get_server_time()["serverTime"])
    local_after_ms = int(time.time() * 1000)
    local_at_measurement_ms = (local_before_ms + local_after_ms) // 2
    client.timestamp_offset = server_time_ms - local_at_measurement_ms


class SpotSessionFactory(ISpotSessionFactory):
    """Mints this module's Spot Testnet read sessions, signed.

    Always Spot Testnet, never parameterized by venue: `TradingVenue` has
    no Spot mainnet member (ADR D8), so there is never a second one to
    choose between.
    """

    def create_account_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        """A signed session, ready to read balances and prices
        (`EPIC-027H`).

        The `cast` only tells mypy what is already true: the object handed
        back satisfies `ISpotSessionClient` structurally, and `Client` is
        untyped third-party (see `pyproject.toml`'s mypy override), so
        returning it as-is would fail `no-any-return` against this method's
        own declared return type.
        """
        client = Client(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            requests_params={"timeout": REQUEST_TIMEOUT_SECONDS},
            testnet=True,
        )
        _sync_timestamp_offset(client)
        return cast(ISpotSessionClient, client)
