"""BUG-168 — an exchange's HTML error page is classified once, at the adapter.

python-binance turns a non-JSON answer into `BinanceAPIException(code=0)` whose
message is the whole page. Every adapter used to forward that text, so the
Bots panel rendered the page and the log carried it six times. The adapter
boundary now answers a short reason with no body (`describe_failure`), and the
connection check names the same answer `MAINTENANCE`.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
    describe_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_commission_rate_reader import (
    FuturesCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_reads import (
    history_read_failures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.market_price_reads import (
    market_price_answer,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_commission_rate_reader import (
    SpotCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate_unavailable_error import (
    CommissionRateUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)

_PAGE = (
    "<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n"
    "<center><h1>502 Bad Gateway</h1></center>\r\n<hr><center>nginx</center>\r\n"
    "</body>\r\n</html>\r\n<!-- a padding to disable MSIE and Chrome friendly "
    "error page -->\r\n"
)
_MARKUP = ("<", ">", "nginx", "padding")


def _html_answer(page: str = _PAGE, status: int = 502) -> BinanceAPIException:
    """The real SDK exception, built the way the SDK builds it."""
    return BinanceAPIException(SimpleNamespace(text=page), status, page)


def _json_rejection() -> BinanceAPIException:
    body = '{"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."}'
    return BinanceAPIException(SimpleNamespace(text=body), 401, body)


def _assert_plain_reason(text: str) -> None:
    assert "502" in text
    assert "Bad Gateway" in text
    for fragment in _MARKUP:
        assert fragment not in text


def test_a_non_json_answer_is_described_without_its_body() -> None:
    _assert_plain_reason(describe_failure(_html_answer()))


def test_a_non_json_answer_without_a_title_still_says_its_status() -> None:
    reason = describe_failure(_html_answer("<html>boom</html>", 503))

    assert "503" in reason
    assert "<" not in reason


def test_a_hostile_title_cannot_carry_markup_into_the_reason() -> None:
    page = "<title>502 <b>Bad</b> <img src=x onerror=1>Gateway</title>"

    reason = describe_failure(_html_answer(page))

    assert "<" not in reason and ">" not in reason


def test_a_json_error_keeps_its_exchange_code_and_message() -> None:
    reason = describe_failure(_json_rejection())

    assert "-2015" in reason
    assert "Invalid API-key" in reason


def test_the_connection_check_calls_an_html_answer_maintenance(caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="App.TradingAdapter"):
        kind = classify_connection_failure(_html_answer(), "Spot Testnet")

    assert kind is ConnectionFailureKind.MAINTENANCE
    assert [r.levelno for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert "<html" not in caplog.text


def test_the_page_is_logged_once_at_debug_and_never_above(caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="App.TradingAdapter"):
        describe_failure(_html_answer())

    bodies = [r for r in caplog.records if "<title>" in r.getMessage()]
    assert [r.levelno for r in bodies] == [logging.DEBUG]


def test_market_price_read_names_the_status_not_the_page() -> None:
    with (
        pytest.raises(MarketPriceUnavailableError) as raised,
        market_price_answer("BTCUSDT Spot best bid and ask"),
    ):
        raise _html_answer()

    _assert_plain_reason(str(raised.value))
    assert "BTCUSDT Spot best bid and ask" in str(raised.value)


def test_history_read_names_the_status_not_the_page() -> None:
    with (
        pytest.raises(AccountHistoryUnavailableError) as raised,
        history_read_failures("Spot order history could not be read"),
    ):
        raise _html_answer()

    _assert_plain_reason(str(raised.value))


class _Sessions:
    """Both venues' session ports, every client call answering the page."""

    def __init__(self) -> None:
        self.client = Mock()
        for method in (
            "get_exchange_info",
            "futures_exchange_info",
            "futures_commission_rate",
            "get_account",
            "futures_change_leverage",
            "futures_account",
        ):
            getattr(self.client, method).side_effect = _html_answer()

    def create_metadata_client(self) -> Any:
        return self.client

    def create_futures_metadata_client(self) -> Any:
        return self.client

    def create_trading_client(self, credentials: ExchangeCredentials) -> Any:
        return self.client

    def create_account_client(self, credentials: ExchangeCredentials) -> Any:
        return self.client


class _Credentials:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="k", api_secret="s"), CredentialsSource.FILE
        )


def test_spot_metadata_provider_answers_a_plain_reason() -> None:
    provider = SpotMetadataProvider(_Sessions(), InMemorySymbolOrderMetadataCache())  # type: ignore[arg-type]

    with pytest.raises(SymbolRulesUnavailableError) as raised:
        provider.get_or_fetch("BTCUSDT")

    _assert_plain_reason(str(raised.value))


def test_futures_metadata_provider_answers_a_plain_reason() -> None:
    provider = FuturesMetadataProvider(_Sessions(), InMemorySymbolOrderMetadataCache())  # type: ignore[arg-type]

    with pytest.raises(SymbolRulesUnavailableError) as raised:
        provider.get_or_fetch("BTCUSDT")

    _assert_plain_reason(str(raised.value))


def test_spot_commission_read_answers_a_plain_reason() -> None:
    reader = SpotCommissionRateReader(_Sessions(), _Credentials())  # type: ignore[arg-type]

    with pytest.raises(CommissionRateUnavailableError) as raised:
        reader.commission_rate("BTCUSDT")

    _assert_plain_reason(str(raised.value))


def test_futures_commission_read_answers_a_plain_reason() -> None:
    reader = FuturesCommissionRateReader(_Sessions(), _Credentials())  # type: ignore[arg-type]

    with pytest.raises(CommissionRateUnavailableError) as raised:
        reader.commission_rate("BTCUSDT")

    _assert_plain_reason(str(raised.value))


def test_account_control_answers_a_plain_reason() -> None:
    control = FuturesAccountControl(_Sessions(), _Credentials())  # type: ignore[arg-type]

    with pytest.raises(AccountControlUnavailableError) as raised:
        control.change_leverage("BTCUSDT", 3)

    _assert_plain_reason(str(raised.value))
