"""`EPIC-028O` — the new reads fail only with their port's errors: an answer
that cannot be read, or one for another symbol, never reaches a desk as a
raw `KeyError` or as another symbol's figure. The round trips through
`python-binance` are in
`tests/integration/infrastructure/binance/test_order_entry_reads_against_fake_server.py`."""

from __future__ import annotations

from typing import Any

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_book_ticker_reader import (
    FuturesBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_mark_price_reader import (
    FuturesMarkPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_book_ticker_reader import (
    SpotBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="key", api_secret="secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


class _Client:
    """Answers each SDK call with what a test hands it; an exception is
    raised instead of returned."""

    def __init__(self, **answers: object) -> None:
        self._answers = answers

    def __getattr__(self, name: str) -> Any:
        answer = self._answers[name]

        def call(**_params: object) -> object:
            if isinstance(answer, Exception):
                raise answer
            return answer

        return call


class _FuturesSessions(FuturesSessionFactory):
    def __init__(self, client: _Client) -> None:
        self._client = client

    def create_futures_metadata_client(self) -> Any:
        return self._client

    def create_trading_client(self, credentials: ExchangeCredentials) -> Any:
        return self._client


class _SpotSessions(SpotSessionFactory):
    def __init__(self, client: _Client) -> None:
        self._client = client

    def create_metadata_client(self) -> Any:
        return self._client


def _bracket(number: int, floor: int, cap: int) -> dict[str, object]:
    return {
        "bracket": number,
        "initialLeverage": 125 // number,
        "notionalCap": cap,
        "notionalFloor": floor,
        "maintMarginRatio": 0.004,
        "cum": 0.0,
    }


@pytest.mark.parametrize(
    ("answers", "read"),
    [
        (
            {"futures_symbol_config": [{"symbol": "ETHUSDT"}]},
            lambda control: control.symbol_setting("BTCUSDT"),
        ),
        (
            {
                "futures_leverage_bracket": {
                    "symbol": "BTCUSDT",
                    "brackets": [_bracket(1, 0, 50_000), _bracket(2, 60_000, 500_000)],
                }
            },
            lambda control: control.leverage_brackets("BTCUSDT"),
        ),
    ],
    ids=["setting-without-the-symbol", "brackets-with-a-gap"],
)
def test_an_unreadable_settings_answer_is_unavailable_and_changes_nothing(
    answers: dict[str, object], read: object
) -> None:
    control = FuturesAccountControl(
        _FuturesSessions(_Client(**answers)), _Credentials()
    )

    with pytest.raises(AccountControlUnavailableError, match="nothing was changed"):
        read(control)  # type: ignore[operator]


_OTHER_SYMBOL_BOOK = {
    "symbol": "ETHUSDT",
    "bidPrice": "1",
    "bidQty": "1",
    "askPrice": "2",
    "askQty": "1",
}


@pytest.mark.parametrize(
    "read",
    [
        lambda answer: FuturesMarkPriceReader(
            _FuturesSessions(_Client(futures_mark_price=answer))
        ).mark_price("BTCUSDT"),
        lambda answer: FuturesBookTickerReader(
            _FuturesSessions(_Client(futures_orderbook_ticker=answer))
        ).best_bid_ask("BTCUSDT"),
        lambda answer: SpotBookTickerReader(
            _SpotSessions(_Client(get_orderbook_ticker=answer))
        ).best_bid_ask("BTCUSDT"),
    ],
    ids=["futures-mark", "futures-book", "spot-book"],
)
@pytest.mark.parametrize(
    ("answer", "cause"),
    [
        ({**_OTHER_SYMBOL_BOOK, "markPrice": "1", "time": 0}, ValueError),
        (RequestsConnectionError("refused"), RequestsConnectionError),
        ({"symbol": "BTCUSDT"}, KeyError),
    ],
    ids=["another-symbol", "no-answer", "missing-field"],
)
def test_a_price_read_fails_only_with_the_ports_error(
    read: object, answer: object, cause: type[Exception]
) -> None:
    with pytest.raises(MarketPriceUnavailableError, match="BTCUSDT") as raised:
        read(answer)  # type: ignore[operator]

    assert isinstance(raised.value.__cause__, cause)
