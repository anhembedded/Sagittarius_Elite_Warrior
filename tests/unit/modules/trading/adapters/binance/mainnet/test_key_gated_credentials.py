"""`EPIC-034` D5 — every credential a mainnet venue's adapters resolve passed the key
gate: a key that can withdraw, or one the gate cannot judge, resolves to no key at
all, so no read and no order goes out on it. The gate and the stored provider are
scripted; the HTTP round trip is the fake-exchange integration test's."""

from __future__ import annotations

from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.api_restrictions_key_gate import (
    ACCEPTED_FOR_SECONDS,
    ApiRestrictionsKeyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_gated_credentials import (
    KeyGatedCredentials,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_KEY = ExchangeCredentials("k", "s")
_STORED = ResolvedCredentials(_KEY, CredentialsSource.KEYRING)
_NO_KEY = ResolvedCredentials(None, CredentialsSource.NONE)


class _Stored(IExchangeCredentialsProvider):
    def __init__(self, resolved: ResolvedCredentials) -> None:
        self.resolved = resolved
        self.saved: list[tuple[str, str]] = []

    def resolve(self) -> ResolvedCredentials:
        return self.resolved

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        self.saved.append((api_key, api_secret))


class _Gate(IKeyPermissionGate):
    def __init__(self, refusal: ConnectionFailureKind | None = None) -> None:
        self.refusal = refusal
        self.asked = 0

    def check(self) -> ConnectFailure | None:
        self.asked += 1
        if self.refusal is None:
            return None
        return ConnectFailure(AccountSource.SPOT_MAINNET, self.refusal)


def test_a_key_the_gate_accepts_resolves_as_stored() -> None:
    resolved = KeyGatedCredentials(_Stored(_STORED), _Gate()).resolve()

    assert resolved == _STORED


def test_a_key_that_can_withdraw_resolves_to_no_key() -> None:
    gate = _Gate(ConnectionFailureKind.WITHDRAWAL_ENABLED)

    resolved = KeyGatedCredentials(_Stored(_STORED), gate).resolve()

    assert resolved == _NO_KEY


def test_a_key_the_gate_could_not_judge_resolves_to_no_key() -> None:
    gate = _Gate(ConnectionFailureKind.NETWORK)

    assert KeyGatedCredentials(_Stored(_STORED), gate).resolve() == _NO_KEY


def test_without_a_stored_key_the_gate_is_not_asked() -> None:
    gate = _Gate()

    resolved = KeyGatedCredentials(_Stored(_NO_KEY), gate).resolve()

    assert resolved == _NO_KEY
    assert gate.asked == 0


def test_saving_goes_to_the_stored_provider() -> None:
    stored = _Stored(_NO_KEY)

    KeyGatedCredentials(stored, _Gate()).save_to_file("a", "b")

    assert stored.saved == [("a", "b")]


def test_emergency_stop_still_gets_its_key_when_the_gate_cannot_reach_the_exchange() -> (
    None
):
    """Emergency stop, a cancel and a close resolve their key through this provider
    like any order. The key was accepted when the session opened; the five-minute
    memory has expired and the exchange does not answer: the key must still resolve
    (`EPIC-034` D5), while a key the exchange says can withdraw does not."""
    now = [0.0]
    read_only = {
        "enableReading": True,
        "enableSpotAndMarginTrading": False,
        "enableWithdrawals": False,
    }
    answer: list[dict[str, bool] | Exception] = [read_only]

    class _Client:
        def get_account_api_permissions(self) -> dict[str, bool]:
            if isinstance(answer[0], Exception):
                raise answer[0]
            return answer[0]

    gate = ApiRestrictionsKeyGate(
        TradingVenue.SPOT_MAINNET,
        lambda: _KEY,
        lambda _venue, _key: _Client(),
        lambda: now[0],
    )
    gated = KeyGatedCredentials(_Stored(_STORED), gate)
    assert gated.resolve() == _STORED  # the session opens

    now[0] += ACCEPTED_FOR_SECONDS
    answer[0] = RequestException("the exchange does not answer")

    assert gated.resolve() == _STORED

    now[0] += ACCEPTED_FOR_SECONDS
    answer[0] = {**read_only, "enableWithdrawals": True}
    assert gated.resolve() == _NO_KEY
