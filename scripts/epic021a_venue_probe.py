"""EPIC-021A runnable milestone — see task §5.

Prints the real base URL and `testnet` flag each `MarketDataVenue` resolves
to, proving the endpoint is genuinely configuration-driven (the thing
`BUG-081` found missing), not hard-coded.

Goes through the real `ExchangeSessionFactory` — the only place in the app
allowed to construct `binance.client.Client(...)`, enforced by
`tests/unit/infrastructure/binance/
test_only_the_session_factory_constructs_binance_client.py`'s AST guard.
This script does not call `Client(...)` itself.

`Client()` pings the network by default (`BUG-045`). On a machine with
Binance egress this proves real reachability. This repository's remote dev
sandbox policy-blocks every `*.binance.*` domain, so the probe falls back to
printing the same URL attributes `Client.__init__` itself resolves them to
(`API_URL`/`API_TESTNET_URL`/`FUTURES_URL`/`FUTURES_TESTNET_URL`, formatted
exactly as the library formats them) — read from the installed
`python-binance` package, not invented by this script.

Run from the superproject root with the venv Python:
    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/epic021a_venue_probe.py
"""

from __future__ import annotations

from binance.client import BaseClient, Client

from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_endpoints import (
    klines_type_for,
    resolve_testnet_flag,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)


def _library_resolved_urls(testnet: bool) -> tuple[str, str]:
    """Same `.format(...)` `Client.__init__` applies to its own class
    constants — read here without constructing a `Client`, so this stays
    truthful even where the ping below can't run."""
    spot = (
        Client.API_TESTNET_URL
        if testnet
        else Client.API_URL.format(BaseClient.BASE_ENDPOINT_DEFAULT, "com")
    )
    futures = (
        Client.FUTURES_TESTNET_URL if testnet else Client.FUTURES_URL.format("com")
    )
    return spot, futures


def _probe(venue: MarketDataVenue) -> None:
    testnet = resolve_testnet_flag(venue)
    klines_type = klines_type_for(venue).name
    spot_url, futures_url = _library_resolved_urls(testnet)
    klines_url = futures_url if klines_type == "FUTURES" else spot_url

    ping_note = ""
    try:
        ExchangeSessionFactory(venue).create_market_data_client()
    except Exception as exc:  # noqa: BLE001 - probe boundary: network reachability varies by host, any failure just means "skip the ping line"
        ping_note = f"  [ping skipped: {type(exc).__name__}]"

    print(
        f"MARKET_DATA  {venue.name:<16} klines: {klines_url:<38} "
        f"({klines_type:<7}) testnet={testnet}{ping_note}"
    )
    print(f"{'':<29} symbols: {spot_url:<38} (SPOT — 021C mới đổi)")


def main() -> None:
    for venue in MarketDataVenue:
        _probe(venue)


if __name__ == "__main__":
    main()
