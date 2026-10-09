"""`BUG-193` — a stored key the exchange refuses is told as refused on every
surface that reads it: the Trading page's State, the account history and the
commission rates, never as a missing key.

@details The key gate resolves a refused key to no credentials, carrying its
refusal (`KeyGatedCredentials`); the readers below get that resolution. Streams
and signing clients word their absent key through the same `unusable_because`
(the architecture guard keeps every other reader from wording it itself).
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.history_reads import (
    require_credentials,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_gated_credentials import (
    KeyGatedCredentials,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_permission_gate import (
    IKeyPermissionGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.connection_state_words import (
    NO_KEY,
    state_of,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
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
    ISpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_REPLY = "-2015 Invalid API-key, IP, or permissions. The key's IP whitelist"


class _Stored(IExchangeCredentialsProvider):
    def __init__(self, stored: bool) -> None:
        self._stored = stored

    def resolve(self) -> ResolvedCredentials:
        if not self._stored:
            return ResolvedCredentials(None, CredentialsSource.NONE)
        return ResolvedCredentials(
            ExchangeCredentials("key", "secret"), CredentialsSource.KEYRING
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used")

    def remove_stored(self) -> None:
        raise AssertionError("not used")


class _Gate(IKeyPermissionGate):
    def __init__(self, refusal: ConnectFailure | None) -> None:
        self._refusal = refusal

    def check(self) -> ConnectFailure | None:
        return self._refusal


def _refused() -> IExchangeCredentialsProvider:
    """A stored mainnet key the exchange answers `-2015` to, as the venue resolves it."""
    refusal = ConnectFailure(
        AccountSource.SPOT_MAINNET, ConnectionFailureKind.KEY_REJECTED, "", _REPLY
    )
    return KeyGatedCredentials(_Stored(True), _Gate(refusal))


def _missing() -> IExchangeCredentialsProvider:
    return KeyGatedCredentials(_Stored(False), _Gate(None))


def _readers(provider: IExchangeCredentialsProvider) -> list[object]:
    return [
        SpotAccountReader(
            Mock(spec=ISpotSessionFactory), provider, TradingVenue.SPOT_MAINNET
        ),
        FuturesAccountReader(
            Mock(spec=ITradingSessionFactory), provider, TradingVenue.FUTURES_MAINNET
        ),
    ]


@pytest.mark.parametrize("index", [0, 1], ids=["spot", "futures"])
def test_the_trading_page_says_a_refused_key_was_refused_not_missing(
    index: int,
) -> None:
    status = _readers(_refused())[index].check_connection()  # type: ignore[attr-defined]

    text, is_error = state_of(status)

    assert status.failure is ConnectionFailureKind.KEY_REJECTED
    assert is_error and text != NO_KEY
    assert "refused the key" in text and "allowlist" in text


@pytest.mark.parametrize("index", [0, 1], ids=["spot", "futures"])
def test_the_trading_page_still_says_no_key_when_there_is_none(index: int) -> None:
    status = _readers(_missing())[index].check_connection()  # type: ignore[attr-defined]

    assert state_of(status) == (NO_KEY, True)


def test_the_history_says_why_the_refused_key_cannot_read_it() -> None:
    with pytest.raises(AccountHistoryUnavailableError) as error:
        require_credentials(_refused(), "Spot")

    assert "-2015" in str(error.value) and "IP whitelist" in str(error.value)
    assert "configured" not in str(error.value)
    assert error.value.kind is ConnectionFailureKind.KEY_REJECTED


def test_the_history_still_says_no_credentials_when_there_are_none() -> None:
    with pytest.raises(AccountHistoryUnavailableError) as error:
        require_credentials(_missing(), "Spot")

    assert str(error.value) == (
        "No Spot credentials configured — cannot read account history."
    )
