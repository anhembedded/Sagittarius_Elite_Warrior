"""`BUG-176` — how each answer of an environment becomes a `KeyStanding`.

A scripted session stands in for python-binance's client; the HTTP round trip over
three fake exchanges is `test_adding_a_key_against_fake_server.py`'s.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance import (
    key_environment_probe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.key_environment_probe import (
    BinanceKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_CREDENTIALS = ExchangeCredentials("K" * 64, "S" * 64)
_ALLOWED = {
    "enableReading": True,
    "enableWithdrawals": False,
    "enableSpotAndMarginTrading": True,
    "enableFutures": True,
}


def _api_error(code: int, message: str = "no") -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message, exc.status_code, exc.response, exc.request = (
        code,
        message,
        401,
        None,
        None,
    )
    return exc


class _Session:
    """Answers the three reads the probe makes; `answer` is returned or raised."""

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.calls: list[str] = []

    def _reply(self, call: str) -> Any:
        self.calls.append(call)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def get_account_api_permissions(self) -> Any:
        return self._reply("apiRestrictions")

    def get_account(self) -> Any:
        return self._reply("spot account")

    def futures_account(self) -> Any:
        return self._reply("futures account")


def _probe(
    answer: Any,
) -> tuple[BinanceKeyEnvironmentProbe, _Session, list[TradingVenue]]:
    session = _Session(answer)
    opened: list[TradingVenue] = []

    def open_session(venue: TradingVenue, _credentials: ExchangeCredentials) -> Any:
        opened.append(venue)
        return session

    return BinanceKeyEnvironmentProbe(open_session), session, opened


@pytest.mark.parametrize(
    ("environment", "venue", "call"),
    [
        (KeyEnvironment.MAINNET, TradingVenue.SPOT_MAINNET, "apiRestrictions"),
        (KeyEnvironment.SPOT_TESTNET, TradingVenue.SPOT_TESTNET, "spot account"),
        (
            KeyEnvironment.FUTURES_TESTNET,
            TradingVenue.FUTURES_TESTNET,
            "futures account",
        ),
    ],
)
def test_each_environment_is_asked_through_its_own_session_with_one_read(
    environment, venue, call
) -> None:
    probe, session, opened = _probe(_ALLOWED)

    verdict = probe.probe(environment, _CREDENTIALS)

    assert verdict.standing is KeyStanding.ACCEPTED
    assert opened == [venue]
    assert session.calls == [call]


def test_mainnet_says_what_the_key_may_do_and_a_testnet_says_nothing_of_permissions() -> (
    None
):
    mainnet, _, _ = _probe(_ALLOWED)
    testnet, _, _ = _probe({})

    permissions = mainnet.probe(KeyEnvironment.MAINNET, _CREDENTIALS).permissions
    assert permissions is not None
    assert (permissions.can_trade_spot, permissions.can_trade_futures) == (True, True)
    assert permissions.can_withdraw is False
    assert testnet.probe(KeyEnvironment.SPOT_TESTNET, _CREDENTIALS).permissions is None


@pytest.mark.parametrize("code", [-2008, -2014])
def test_an_unknown_key_or_a_bad_key_format_is_an_unknown_key(code, caplog) -> None:
    probe, _, _ = _probe(_api_error(code))

    with caplog.at_level(logging.INFO):
        verdict = probe.probe(KeyEnvironment.SPOT_TESTNET, _CREDENTIALS)

    assert verdict.standing is KeyStanding.UNKNOWN
    assert "unclassified exception" not in caplog.text  # not the catch-all bucket


def test_minus_2015_is_a_known_key_refused_here() -> None:
    probe, _, _ = _probe(_api_error(-2015))

    assert (
        probe.probe(KeyEnvironment.MAINNET, _CREDENTIALS).standing
        is KeyStanding.REFUSED
    )


@pytest.mark.parametrize(
    ("raised", "kind"),
    [
        (_api_error(-1021), ConnectionFailureKind.CLOCK_SKEW),
        (_api_error(-1022), ConnectionFailureKind.BAD_SIGNATURE),
        (RequestsConnectionError("down"), ConnectionFailureKind.NETWORK),
        (BinanceRequestException("garbled"), ConnectionFailureKind.NETWORK),
    ],
)
def test_no_answer_about_the_key_is_unreachable_and_says_why(raised, kind) -> None:
    probe, _, _ = _probe(raised)

    verdict = probe.probe(KeyEnvironment.FUTURES_TESTNET, _CREDENTIALS)

    assert verdict.standing is KeyStanding.UNREACHABLE
    assert verdict.failure is kind


def test_an_answer_that_is_not_what_binance_documents_is_never_read_as_accepted() -> (
    None
):
    probe, _, _ = _probe({"enableReading": "yes"})

    verdict = probe.probe(KeyEnvironment.MAINNET, _CREDENTIALS)

    assert verdict.standing is KeyStanding.UNREACHABLE


def test_the_log_names_the_key_by_fingerprint_never_the_secret(caplog) -> None:
    probe, _, _ = _probe(_api_error(-2008))

    with caplog.at_level(logging.INFO):
        probe.probe(KeyEnvironment.MAINNET, _CREDENTIALS)

    assert "KKKK…KKKK" in caplog.text
    assert "S" * 8 not in caplog.text
    assert "K" * 8 not in caplog.text


def test_a_key_python_cannot_send_leaks_nowhere_in_the_log(caplog) -> None:
    """The reviewer's blocker on PR #423: a key with a character outside Latin-1 makes
    `requests` raise `UnicodeEncodeError`, whose repr holds the header value, the
    whole key."""
    key = "k" * 30 + "é€" + "z" * 30
    try:
        key.encode("latin-1")
    except UnicodeEncodeError as exc:
        raised = exc
    probe, _, _ = _probe(raised)

    with caplog.at_level(logging.DEBUG):
        verdict = probe.probe(KeyEnvironment.MAINNET, ExchangeCredentials(key, "s"))

    assert verdict.standing is KeyStanding.UNREACHABLE
    assert "kkkkkkkkkk" not in caplog.text
    assert "zzzzzzzzzz" not in caplog.text


def test_a_refusal_carries_the_exchanges_code_and_message_then_the_hint() -> None:
    """The one wording (`describe_failure`) the Connect step and the log use."""
    unknown, _, _ = _probe(_api_error(-2008, "Invalid Api-Key ID."))
    refused, _, _ = _probe(_api_error(-2015, "Invalid API-key, IP, or permissions."))

    unknown_reason = unknown.probe(KeyEnvironment.MAINNET, _CREDENTIALS).reason
    refused_reason = refused.probe(KeyEnvironment.MAINNET, _CREDENTIALS).reason

    assert unknown_reason.startswith("-2008 Invalid Api-Key ID.")
    assert "does not work on mainnet" in unknown_reason
    assert refused_reason.startswith("-2015 Invalid API-key, IP, or permissions.")
    assert "192.168.x.x" in refused_reason


def test_the_codes_that_mean_unknown_are_the_shared_modules_not_a_copy() -> None:
    assert not hasattr(key_environment_probe, "_UNKNOWN_KEY_CODES")
    assert {-2008, -2014} == key_environment_probe.UNKNOWN_KEY_CODES
