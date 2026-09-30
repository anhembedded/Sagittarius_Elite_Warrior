"""`EPIC-028F` — `FuturesCommissionRateReader` and `SpotCommissionRateReader`:
what each reads, and how a failed read is reported.

@details The session factories and the credentials provider are small
subclasses of their ports; only the raw SDK client, which is third-party, is
a `Mock`. The round trip over HTTP is
`tests/integration/infrastructure/binance/test_account_controls_against_fake_server.py`'s.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_commission_rate_reader import (
    FuturesCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_commission_rate_reader import (
    SpotCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate_unavailable_error import (
    CommissionRateUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)


class _Credentials(IExchangeCredentialsProvider):
    def __init__(self, configured: bool = True) -> None:
        self._credentials = (
            ExchangeCredentials(api_key="key", api_secret="secret")
            if configured
            else None
        )

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.FILE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used")


class _FuturesSessions(ITradingSessionFactory):
    def __init__(self, client: Any) -> None:
        self._client = client

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        return self._client


class _SpotSessions(ISpotSessionFactory):
    def __init__(self, client: Any) -> None:
        self._client = client

    def create_account_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        return self._client

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        raise AssertionError("a commission read uses the account client")


def _api_error() -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = -2015
    exc.message = "Invalid API-key, IP, or permissions for action."
    exc.status_code = 401
    exc.response = None
    exc.request = None
    return exc


def test_futures_reads_the_symbols_own_rates() -> None:
    client = Mock()
    client.futures_commission_rate.return_value = {
        "symbol": "BTCUSDT",
        "makerCommissionRate": "0.0002",
        "takerCommissionRate": "0.0005",
    }

    rate = FuturesCommissionRateReader(
        _FuturesSessions(client), _Credentials()
    ).commission_rate("BTCUSDT")

    assert rate == CommissionRate("BTCUSDT", Decimal("0.0002"), Decimal("0.0005"))
    client.futures_commission_rate.assert_called_once_with(symbol="BTCUSDT")


def test_spot_reads_the_accounts_rates_for_any_symbol() -> None:
    client = Mock()
    client.get_account.return_value = {
        "commissionRates": {
            "maker": "0.00100000",
            "taker": "0.00150000",
            "buyer": "0.00000000",
            "seller": "0.00000000",
        },
        "balances": [],
    }

    rate = SpotCommissionRateReader(
        _SpotSessions(client), _Credentials()
    ).commission_rate("ETHUSDT")

    assert rate == CommissionRate("ETHUSDT", Decimal("0.001"), Decimal("0.0015"))


def test_a_negative_maker_rate_is_kept_as_the_rebate_it_is() -> None:
    client = Mock()
    client.futures_commission_rate.return_value = {
        "symbol": "BTCUSDT",
        "makerCommissionRate": "-0.0001",
        "takerCommissionRate": "0.0004",
    }

    rate = FuturesCommissionRateReader(
        _FuturesSessions(client), _Credentials()
    ).commission_rate("BTCUSDT")

    assert rate.maker == Decimal("-0.0001")


@pytest.mark.parametrize(
    "failure",
    [_api_error(), RequestsConnectionError("reset"), KeyError("makerCommissionRate")],
)
def test_a_failed_futures_read_raises_the_readers_own_error(
    failure: Exception,
) -> None:
    client = Mock()
    client.futures_commission_rate.side_effect = failure

    with pytest.raises(CommissionRateUnavailableError) as raised:
        FuturesCommissionRateReader(
            _FuturesSessions(client), _Credentials()
        ).commission_rate("BTCUSDT")

    assert raised.value.__cause__ is failure


def test_a_futures_answer_that_is_not_an_object_raises_the_readers_own_error() -> None:
    """PR #299 review, finding 3: a list where an object belongs raised a raw
    `TypeError`."""
    client = Mock()
    client.futures_commission_rate.return_value = []

    with pytest.raises(CommissionRateUnavailableError):
        FuturesCommissionRateReader(
            _FuturesSessions(client), _Credentials()
        ).commission_rate("BTCUSDT")


def test_a_spot_account_without_commission_rates_raises_the_readers_own_error() -> None:
    client = Mock()
    client.get_account.return_value = {"balances": []}

    with pytest.raises(CommissionRateUnavailableError):
        SpotCommissionRateReader(_SpotSessions(client), _Credentials()).commission_rate(
            "BTCUSDT"
        )


def test_no_credentials_raises_before_any_request() -> None:
    futures, spot = Mock(), Mock()

    with pytest.raises(CommissionRateUnavailableError):
        FuturesCommissionRateReader(
            _FuturesSessions(futures), _Credentials(configured=False)
        ).commission_rate("BTCUSDT")
    with pytest.raises(CommissionRateUnavailableError):
        SpotCommissionRateReader(
            _SpotSessions(spot), _Credentials(configured=False)
        ).commission_rate("BTCUSDT")
    with pytest.raises(AccountControlUnavailableError):
        FuturesAccountControl(
            _FuturesSessions(futures), _Credentials(configured=False)
        ).change_margin_type("BTCUSDT", MarginType.CROSSED)

    assert futures.method_calls == []
    assert spot.method_calls == []
