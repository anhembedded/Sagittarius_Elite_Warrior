"""`EPIC-034` D11 — one function builds every venue's python-binance `Client`: the
venue says `testnet=True` or `testnet=False`, which API family measures the clock,
and whether the construction-time ping is wanted. Nothing else differs between a
mainnet venue and its testnet twin."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance import (
    binance_client_builder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_client_builder import (
    new_client,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    REQUEST_TIMEOUT_SECONDS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_KEYS = ExchangeCredentials("api-key", "api-secret")
_TRADING = [v for v in TradingVenue if v.supports_order_submission]
_FUTURES = [TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET]
_SPOT = [TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET]


class _Client:
    """What `Client` is to the builder: built with keywords, asked for the server's
    time once, through the call of its own API family."""

    built: ClassVar[list[dict[str, Any]]] = []
    time_calls: ClassVar[list[str]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.timestamp_offset = 0
        _Client.built.append(kwargs)

    def get_server_time(self) -> dict[str, Any]:
        _Client.time_calls.append("spot")
        return {"serverTime": 10**12}

    def futures_time(self) -> dict[str, Any]:
        _Client.time_calls.append("futures")
        return {"serverTime": 10**12}


@pytest.fixture(autouse=True)
def _client(monkeypatch: pytest.MonkeyPatch) -> None:
    _Client.built = []
    _Client.time_calls = []
    monkeypatch.setattr(binance_client_builder, "Client", _Client)


@pytest.mark.parametrize("venue", _TRADING)
def test_the_testnet_flag_is_the_venues_for_a_signed_session(
    venue: TradingVenue,
) -> None:
    new_client(venue, _KEYS)

    assert _Client.built[0]["testnet"] is venue.is_testnet
    assert (venue.is_testnet, venue.is_mainnet) in {(True, False), (False, True)}


@pytest.mark.parametrize("venue", _TRADING)
def test_the_testnet_flag_is_the_venues_for_an_unsigned_session(
    venue: TradingVenue,
) -> None:
    new_client(venue)

    assert _Client.built[0]["testnet"] is venue.is_testnet


@pytest.mark.parametrize("venue", _TRADING)
def test_a_signed_session_carries_the_key_the_timeout_and_a_measured_offset(
    venue: TradingVenue,
) -> None:
    client = new_client(venue, _KEYS)

    kwargs = _Client.built[0]
    assert (kwargs["api_key"], kwargs["api_secret"]) == ("api-key", "api-secret")
    assert kwargs["requests_params"] == {"timeout": REQUEST_TIMEOUT_SECONDS}
    assert client.timestamp_offset != 0  # type: ignore[attr-defined]


@pytest.mark.parametrize("venue", _FUTURES)
def test_a_futures_session_measures_the_clock_on_the_futures_api_and_never_pings(
    venue: TradingVenue,
) -> None:
    new_client(venue, _KEYS)

    assert _Client.time_calls == ["futures"]
    assert _Client.built[0]["ping"] is False


@pytest.mark.parametrize("venue", _SPOT)
def test_a_spot_session_measures_the_clock_on_the_spot_api_and_pings(
    venue: TradingVenue,
) -> None:
    new_client(venue, _KEYS)

    assert _Client.time_calls == ["spot"]
    assert _Client.built[0]["ping"] is True


@pytest.mark.parametrize("venue", _TRADING)
def test_an_unsigned_session_has_no_key_no_ping_and_no_clock_measurement(
    venue: TradingVenue,
) -> None:
    client = new_client(venue)

    kwargs = _Client.built[0]
    assert kwargs["api_key"] is None
    assert kwargs["ping"] is False
    assert _Client.time_calls == []
    assert client.timestamp_offset == 0  # type: ignore[attr-defined]


def test_a_disabled_venue_has_no_session_to_open() -> None:
    with pytest.raises(ValueError, match="no session"):
        new_client(TradingVenue.DISABLED)


# -- the factories only choose the family; the venue is the whole difference ---


@pytest.mark.parametrize("venue", _FUTURES)
def test_a_futures_factory_opens_every_session_on_its_own_venue(
    venue: TradingVenue,
) -> None:
    factory = FuturesSessionFactory(venue)

    factory.create_trading_client(_KEYS)
    factory.create_futures_metadata_client()

    assert [b["testnet"] for b in _Client.built] == [venue.is_testnet] * 2


@pytest.mark.parametrize("venue", _SPOT)
def test_a_spot_factory_opens_every_session_on_its_own_venue(
    venue: TradingVenue,
) -> None:
    factory = SpotSessionFactory(venue)

    factory.create_account_client(_KEYS)
    factory.create_trading_client(_KEYS)
    factory.create_metadata_client()

    assert [b["testnet"] for b in _Client.built] == [venue.is_testnet] * 3


@pytest.mark.parametrize("venue", _SPOT)
def test_a_futures_factory_refuses_a_spot_venue(venue: TradingVenue) -> None:
    with pytest.raises(ValueError, match="not a Futures venue"):
        FuturesSessionFactory(venue)


@pytest.mark.parametrize("venue", _FUTURES)
def test_a_spot_factory_refuses_a_futures_venue(venue: TradingVenue) -> None:
    with pytest.raises(ValueError, match="not a Spot venue"):
        SpotSessionFactory(venue)
