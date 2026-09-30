"""`EPIC-028F` — `FuturesAccountControl` and both commission readers over a
real HTTP round trip to the fake exchange server.

@details The server runs on this machine and ignores signatures
(`tests/sanity/binance_fake_server.py`). What this proves is the request
shapes the SDK sends, Binance's error bodies turning into the port's errors,
and the payload mapping, end to end.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_commission_rate_reader import (
    FuturesCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_commission_rate_reader import (
    SpotCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")


@contextmanager
def _fake_exchange() -> Iterator[None]:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        yield


def _control() -> FuturesAccountControl:
    return FuturesAccountControl(FuturesSessionFactory(), _Credentials())


def test_a_leverage_change_reads_back_the_exchanges_confirmation() -> None:
    with _fake_exchange():
        applied = _control().change_leverage("BTCUSDT", 10)

    assert applied == LeverageSetting("BTCUSDT", 10, Decimal(10000000))


def test_a_leverage_the_exchange_refuses_carries_its_code() -> None:
    with _fake_exchange(), pytest.raises(AccountControlRejectedError) as raised:
        _control().change_leverage("BTCUSDT", 200)

    assert raised.value.code == -4028


def test_changing_to_isolated_twice_is_one_change_and_no_error() -> None:
    """The second request is refused by the exchange with `-4046`, which the
    port reads as "already in effect"."""
    with _fake_exchange():
        control = _control()
        first = control.change_margin_type("BTCUSDT", MarginType.ISOLATED)
        second = control.change_margin_type("BTCUSDT", MarginType.ISOLATED)

    assert first is MarginType.ISOLATED
    assert second is MarginType.ISOLATED


def test_each_venue_reads_its_own_commission_rates() -> None:
    with _fake_exchange():
        futures = FuturesCommissionRateReader(
            FuturesSessionFactory(), _Credentials()
        ).commission_rate("BTCUSDT")
        spot = SpotCommissionRateReader(
            SpotSessionFactory(), _Credentials()
        ).commission_rate("BTCUSDT")

    assert futures == CommissionRate("BTCUSDT", Decimal("0.0002"), Decimal("0.0005"))
    assert spot == CommissionRate("BTCUSDT", Decimal("0.001"), Decimal("0.001"))
