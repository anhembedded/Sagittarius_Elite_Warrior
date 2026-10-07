"""BUG-167 — Binance `-2015` means "key, IP or permissions rejected", never "expired".

A real (mainnet) key sent to the testnet is unknown there and gets `-2015`; the
app used to call that `KEY_EXPIRED` and tell the owner the key had expired.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.connection_words import (
    failure_text,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_CREDENTIALS = ExchangeCredentials(api_key="k", api_secret="s")


def _rejection() -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = -2015
    exc.message = "Invalid API-key, IP, or permissions for action"
    exc.status_code = 401
    exc.response = None
    exc.request = None
    return exc


def _futures_reader() -> FuturesAccountReader:
    client = Mock()
    client.futures_ping.side_effect = _rejection()
    return _build(FuturesAccountReader, "create_trading_client", client)


def _spot_reader() -> SpotAccountReader:
    client = Mock()
    client.ping.side_effect = _rejection()
    return _build(SpotAccountReader, "create_account_client", client)


def _build(reader_cls, factory_method: str, client: Mock):
    factory = Mock()
    getattr(factory, factory_method).return_value = client
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    return reader_cls(factory, provider)


def _status(venue: TradingVenue, kind: ConnectionFailureKind):
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=False,
        failure=kind,
        server_time_skew_ms=None,
        usdt_balance=Decimal(0),
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )


@pytest.mark.parametrize("make_reader", [_futures_reader, _spot_reader])
def test_minus_2015_from_either_reader_is_a_rejected_key(make_reader, caplog):
    with caplog.at_level("INFO", logger="App.TradingAdapter"):
        status = make_reader().check_connection()

    assert status.failure is ConnectionFailureKind.KEY_REJECTED
    assert "-2015" in caplog.text
    assert "KEY_REJECTED" in caplog.text


def test_no_failure_kind_claims_a_key_expired():
    assert not [k for k in ConnectionFailureKind if "EXPIRED" in k.name]


@pytest.mark.parametrize(
    "venue", [TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET]
)
def test_the_words_never_say_expired_and_name_the_causes(venue):
    status = _status(venue, ConnectionFailureKind.KEY_REJECTED)

    for text in (failure_text(status), format_exchange_connection_status(status)):
        assert text is not None
        lowered = text.lower()
        assert "expire" not in lowered
        assert "testnet" in lowered
        assert "mainnet" in lowered
        assert "whitelist" in lowered or "allowlist" in lowered
        assert "permission" in lowered
