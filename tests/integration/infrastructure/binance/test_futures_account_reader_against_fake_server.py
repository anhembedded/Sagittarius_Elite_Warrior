"""`EPIC-021D` — `FuturesAccountReader` against a real HTTP round trip.

@details Same reasoning as the other `EPIC-021` fake-server integration
tests: `create_trading_client()` constructs a real, signed
`binance.client.Client`, so this needs a local substitute rather than a
hand-written port double.

**What this does and does not prove**: `tests/sanity/binance_fake_server.py`
serves fixed responses regardless of the request's signature/timestamp — it
proves the whole call chain (client construction, signing headers attached,
URL routing, JSON parsing, VO assembly) runs unchanged end to end, the same
guarantee `EPIC-009` D6 exists for. It does NOT prove Binance's own
signature *validation* — there is no way to fake a real rejection without
implementing HMAC verification, which would make the fixture itself a thing
that could have its own bugs. The failure-classification logic (which
error code maps to which `ConnectionFailureKind`) is proven separately, and
purely at the unit level, in `test_futures_account_reader.py`.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_account_reader import (
    FuturesAccountReader,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server


class _FakeCredentialsProvider:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this test")


def test_check_connection_round_trips_the_fake_servers_account_snapshot():
    with (
        run_binance_fake_server() as urls,
        # `Client(...)`'s constructor pings on construction by default
        # (`ping=True`) — always the SPOT path (`API_TESTNET_URL`).
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = ExchangeSessionFactory(MarketDataVenue.MAINNET_PUBLIC)
        reader = FuturesAccountReader(session_factory, _FakeCredentialsProvider())

        status = reader.check_connection()

        assert status.venue is TradingVenue.FUTURES_TESTNET
        assert status.reachable is True
        assert status.failure is None
        assert status.usdt_balance == Decimal("15000.00000000")
        assert status.position_mode is PositionMode.ONE_WAY
        assert status.open_position_count == 0
        assert status.server_time_skew_ms is not None
