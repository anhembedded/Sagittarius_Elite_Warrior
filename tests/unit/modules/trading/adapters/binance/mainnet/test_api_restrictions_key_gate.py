"""`EPIC-034` D5, D11 — the key gate: what a mainnet key may do is asked first, a key
that can withdraw is refused, and every other key is accepted (mainnet trades
exactly like testnet). A scripted client records the calls it gets; the HTTP round
trip is the integration test's."""

from __future__ import annotations

from typing import Any

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.api_restrictions_key_gate import (
    ApiRestrictionsKeyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_client import (
    IKeyPermissionsClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_parser import (
    parse_key_permissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_VENUES = [TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET]
_BOTH = pytest.mark.parametrize("venue", _VENUES)
_READ_ONLY = {
    "enableReading": True,
    "enableSpotAndMarginTrading": False,
    "enableWithdrawals": False,
}
_KEY = ExchangeCredentials("k", "s")


class _Client:
    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self.answer = answer
        self.calls = 0

    def get_account_api_permissions(self) -> dict[str, Any]:
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _api_error(code: int) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message, exc.status_code, exc.response, exc.request = (
        code,
        f"error {code}",
        400,
        None,
        None,
    )
    return exc


def _gate(
    venue: TradingVenue,
    answer: dict[str, Any] | Exception,
    credentials: ExchangeCredentials | None = _KEY,
) -> tuple[ApiRestrictionsKeyGate, _Client, list[TradingVenue]]:
    client = _Client(answer)
    opened: list[TradingVenue] = []

    def clients(opened_for: TradingVenue, _credentials: ExchangeCredentials):
        opened.append(opened_for)
        return client

    return ApiRestrictionsKeyGate(venue, lambda: credentials, clients), client, opened


@_BOTH
def test_a_read_only_key_is_accepted(venue: TradingVenue) -> None:
    gate, client, opened = _gate(venue, _READ_ONLY)

    assert gate.check() is None
    assert client.calls == 1
    assert opened == [venue]  # the session of this venue, not another


@_BOTH
def test_a_key_that_can_trade_is_accepted_too(venue: TradingVenue) -> None:
    trading = {**_READ_ONLY, "enableSpotAndMarginTrading": True, "enableFutures": True}

    gate, _, _ = _gate(venue, trading)

    assert gate.check() is None


@_BOTH
def test_a_key_that_can_withdraw_is_refused(venue: TradingVenue) -> None:
    gate, _, _ = _gate(venue, {**_READ_ONLY, "enableWithdrawals": True})

    assert gate.check() == ConnectFailure(
        AccountSource.for_venue(venue),
        ConnectionFailureKind.WITHDRAWAL_ENABLED,
        "withdrawals",
    )


def test_a_key_that_can_withdraw_and_trade_is_refused_for_withdrawing() -> None:
    both = {**_READ_ONLY, "enableWithdrawals": True, "enableSpotAndMarginTrading": True}

    refused = _gate(TradingVenue.SPOT_MAINNET, both)[0].check()

    assert refused is not None
    assert refused.kind is ConnectionFailureKind.WITHDRAWAL_ENABLED


@_BOTH
def test_no_key_is_not_configured_and_nothing_is_opened(venue: TradingVenue) -> None:
    gate, client, opened = _gate(venue, _READ_ONLY, credentials=None)

    assert gate.check() == ConnectFailure(
        AccountSource.for_venue(venue), ConnectionFailureKind.NOT_CONFIGURED
    )
    assert (client.calls, opened) == (0, [])


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        (-2015, ConnectionFailureKind.KEY_REJECTED),
        (-1022, ConnectionFailureKind.BAD_SIGNATURE),
        (-1021, ConnectionFailureKind.CLOCK_SKEW),
    ],
)
def test_the_exchange_rejecting_the_key_is_named(
    code: int, kind: ConnectionFailureKind
) -> None:
    gate, _, _ = _gate(TradingVenue.SPOT_MAINNET, _api_error(code))

    assert gate.check() == ConnectFailure(AccountSource.SPOT_MAINNET, kind, "")


def test_a_session_that_cannot_be_opened_is_named_by_its_error() -> None:
    def refusing(_venue: TradingVenue, _credentials: ExchangeCredentials):
        raise _api_error(-2015)

    gate = ApiRestrictionsKeyGate(TradingVenue.SPOT_MAINNET, lambda: _KEY, refusing)

    refused = gate.check()

    assert refused is not None and refused.kind is ConnectionFailureKind.KEY_REJECTED


def test_a_withdrawal_flag_the_exchange_leaves_out_refuses_the_key() -> None:
    payload = {k: v for k, v in _READ_ONLY.items() if k != "enableWithdrawals"}

    refused = _gate(TradingVenue.SPOT_MAINNET, payload)[0].check()

    assert refused is not None
    assert refused.detail == "the key's permissions"
    assert refused.kind is not ConnectionFailureKind.NOT_CONFIGURED


def test_an_unreadable_answer_is_a_named_failure_not_a_pass() -> None:
    refused = _gate(TradingVenue.SPOT_MAINNET, {"enableWithdrawals": "no"})[0].check()

    assert refused is not None and refused.kind is ConnectionFailureKind.NETWORK


def test_a_testnet_venue_has_no_such_gate() -> None:
    # The gate is built for mainnet venues only; it would still name its own source.
    gate, _, _ = _gate(TradingVenue.SPOT_TESTNET, _READ_ONLY)

    assert gate.check() is None


# -- the permissions parser ---------------------------------------------------


def test_the_parser_reads_the_three_flags_the_gate_decides_on() -> None:
    permissions = parse_key_permissions(
        {
            "enableReading": True,
            "enableSpotAndMarginTrading": True,
            "enableWithdrawals": False,
        }
    )

    assert (
        permissions.can_read,
        permissions.can_trade_spot,
        permissions.can_withdraw,
    ) == (True, True, False)


@pytest.mark.parametrize("missing", list(_READ_ONLY))
def test_a_missing_flag_is_an_error_never_a_false(missing: str) -> None:
    payload = {k: v for k, v in _READ_ONLY.items() if k != missing}

    with pytest.raises(KeyError):
        parse_key_permissions(payload)


@pytest.mark.parametrize("junk", ["false", 0, None])
def test_a_flag_that_is_not_a_boolean_is_an_error(junk: object) -> None:
    with pytest.raises(TypeError):
        parse_key_permissions({**_READ_ONLY, "enableWithdrawals": junk})


def test_the_client_port_lists_exactly_the_one_read_the_gate_makes() -> None:
    members = {
        name
        for name in vars(IKeyPermissionsClient)
        if not name.startswith("_") and callable(getattr(IKeyPermissionsClient, name))
    }

    assert members == {"get_account_api_permissions"}
