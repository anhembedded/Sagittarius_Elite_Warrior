"""`EPIC-034` D11 — the `testnet` flag of a venue's client is the venue's own.

@details Split from `test_module_venue_contexts_binding.py` (the 400-line
ceiling): through the real assembly, from a venue's own key to python-binance's
`Client(...)` call, nothing but the venue decides the flag.
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance import (
    binance_client_builder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    FUTURES_MAINNET_ENV_API_KEY,
    FUTURES_MAINNET_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
    SPOT_MAINNET_ENV_API_KEY,
    SPOT_MAINNET_ENV_API_SECRET,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_contexts_world import (
    both_venues,
)

_KEY_NAMES = {
    TradingVenue.FUTURES_TESTNET: (FUTURES_ENV_API_KEY, FUTURES_ENV_API_SECRET),
    TradingVenue.SPOT_TESTNET: (SPOT_ENV_API_KEY, SPOT_ENV_API_SECRET),
    TradingVenue.FUTURES_MAINNET: (
        FUTURES_MAINNET_ENV_API_KEY,
        FUTURES_MAINNET_ENV_API_SECRET,
    ),
    TradingVenue.SPOT_MAINNET: (SPOT_MAINNET_ENV_API_KEY, SPOT_MAINNET_ENV_API_SECRET),
}


class _RefusingClient:
    """python-binance's `Client` as the builder meets it: it records how it was
    built and then fails like an unreachable exchange, so no request leaves."""

    built: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, **kwargs: Any) -> None:
        _RefusingClient.built.append(kwargs)
        raise RequestsConnectionError("no network in a unit test")


@pytest.mark.parametrize("venue", list(_KEY_NAMES))
def test_testnet_false_reaches_the_client_of_a_mainnet_venue_and_true_the_testnets(
    monkeypatch: pytest.MonkeyPatch, venue: TradingVenue
) -> None:
    """`EPIC-034` D11 — through the real assembly, from the venue's own key to the
    `Client(...)` call: the flag is the venue's and nothing else decides it."""
    _RefusingClient.built = []
    monkeypatch.setattr(binance_client_builder, "Client", _RefusingClient)
    monkeypatch.setattr(time, "sleep", lambda _s: None)  # opening a session retries
    for key_name, secret_name in _KEY_NAMES.values():
        monkeypatch.delenv(key_name, raising=False)
        monkeypatch.delenv(secret_name, raising=False)
    key_name, secret_name = _KEY_NAMES[venue]
    monkeypatch.setenv(key_name, "key")
    monkeypatch.setenv(secret_name, "secret")
    contexts = both_venues().resolve(IVenueContexts)

    status = contexts.get(venue).account_reader.check_connection()

    assert status.venue is venue
    assert {kwargs["testnet"] for kwargs in _RefusingClient.built} == {venue.is_testnet}
    # A mainnet key is used only once the key gate has judged it (`EPIC-034` D5):
    # the gate's own session is the one built here, it cannot be judged, and so
    # the account read sees no usable key and says why (`BUG-193`: the gate could
    # not ask, which is a network failure, never "no key"). A testnet reaches the
    # exchange itself.
    assert status.failure is ConnectionFailureKind.NETWORK
