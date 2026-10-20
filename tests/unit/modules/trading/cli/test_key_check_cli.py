"""`BOT-200` — `key check` prints which venue a key is for, or why none, exits by the
exit-code table, and never prints or logs the key or the secret in any outcome."""

from __future__ import annotations

import argparse
import json
import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.trading.cli.key_check_report import (
    REFUSAL_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.cli.key_cli_handler import (
    run_key_check,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_check import (
    KeyCheckRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    KeyEnvironment,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.cli.key_check_world import (
    REFUSED_REASON,
    SENTINEL_KEY,
    SENTINEL_SECRET,
    SENTINELS,
    HandlerDispatcher,
    ScriptedProbe,
    accepted,
    mainnet_accepts,
    refused,
    sentinel_credentials,
    unknown,
    unreachable,
)

_ENV = KeyEnvironment

#: Every outcome `key check` has: what the exchange says, the input, and the exit status.
_SCENARIOS = {
    "spot-testnet": (
        {_ENV.SPOT_TESTNET: accepted(_ENV.SPOT_TESTNET)},
        sentinel_credentials(),
        None,
    ),
    "futures-testnet": (
        {
            _ENV.SPOT_TESTNET: unknown(_ENV.SPOT_TESTNET),
            _ENV.FUTURES_TESTNET: accepted(_ENV.FUTURES_TESTNET),
        },
        sentinel_credentials(),
        None,
    ),
    "mainnet-both": (
        {_ENV.MAINNET: mainnet_accepts(spot=True, futures=True)},
        sentinel_credentials(),
        None,
    ),
    "mainnet-spot": (
        {_ENV.MAINNET: mainnet_accepts(spot=True)},
        sentinel_credentials(),
        None,
    ),
    "mainnet-futures": (
        {_ENV.MAINNET: mainnet_accepts(futures=True)},
        sentinel_credentials(),
        None,
    ),
    "withdrawal-enabled": (
        {_ENV.MAINNET: mainnet_accepts(spot=True, withdraw=True)},
        sentinel_credentials(),
        ExitCode.CONFIGURATION,
    ),
    "no-trading-permission": (
        {_ENV.MAINNET: mainnet_accepts()},
        sentinel_credentials(),
        ExitCode.CONFIGURATION,
    ),
    "nobody-accepts": (
        {
            _ENV.MAINNET: unknown(_ENV.MAINNET),
            _ENV.SPOT_TESTNET: refused(_ENV.SPOT_TESTNET),
            _ENV.FUTURES_TESTNET: unknown(_ENV.FUTURES_TESTNET),
        },
        sentinel_credentials(),
        ExitCode.CONFIGURATION,
    ),
    "an-environment-did-not-answer": (
        {
            _ENV.MAINNET: unknown(_ENV.MAINNET),
            _ENV.SPOT_TESTNET: unreachable(_ENV.SPOT_TESTNET),
            _ENV.FUTURES_TESTNET: unknown(_ENV.FUTURES_TESTNET),
        },
        sentinel_credentials(),
        ExitCode.EXCHANGE,
    ),
    "empty-secret": ({}, ExchangeCredentials(SENTINEL_KEY, ""), ExitCode.USAGE),
    "a-space-in-the-key": (
        {},
        ExchangeCredentials(SENTINEL_KEY + " x", SENTINEL_SECRET),
        ExitCode.USAGE,
    ),
}


def _run(scenario: str, *, as_json: bool = False) -> int:
    answers, credentials, _ = _SCENARIOS[scenario]
    outcome = run_key_check(
        credentials,
        HandlerDispatcher(ScriptedProbe(answers)),
        ReportPrinter(ReportFormats.default()),
        argparse.Namespace(json=as_json, format=None),
    )
    return int(ExitCode.SUCCESS) if outcome is None else int(outcome.code)


def _data(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["schema"] == "sew.key/1"
    return envelope["data"]


@pytest.mark.parametrize("scenario", list(_SCENARIOS))
def test_the_exit_status_follows_the_exit_code_table(scenario) -> None:
    status = _run(scenario)

    expected = _SCENARIOS[scenario][2]
    assert status == int(ExitCode.SUCCESS if expected is None else expected)


@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
@pytest.mark.parametrize("scenario", list(_SCENARIOS))
def test_neither_the_key_nor_the_secret_reaches_the_output_or_the_log_in_any_outcome(
    scenario, as_json, capsys, caplog
) -> None:
    caplog.set_level(logging.DEBUG)

    _run(scenario, as_json=as_json)

    printed = capsys.readouterr()
    everything = printed.out + printed.err + caplog.text
    assert everything, "the command printed nothing"
    for sentinel in SENTINELS:
        assert sentinel not in everything
    for record in caplog.records:
        assert not any(s in record.getMessage() for s in SENTINELS)
        assert not any(s in repr(record.args) for s in SENTINELS)


def test_a_testnet_key_is_reported_with_its_venue(capsys) -> None:
    _run("futures-testnet", as_json=True)

    body = _data(capsys)
    assert body["ok"] is True
    assert body["venues"] == ["futures_testnet"]
    assert body["environment"] == "futures_testnet"
    assert body["refusal"] is None


def test_a_mainnet_key_that_can_trade_both_markets_names_both_venues(capsys) -> None:
    _run("mainnet-both", as_json=True)

    body = _data(capsys)
    assert body["venues"] == ["spot_mainnet", "futures_mainnet"]
    assert body["environment"] == "mainnet"


def test_the_text_report_names_the_venue_and_says_nothing_was_written(capsys) -> None:
    _run("mainnet-spot")

    out = capsys.readouterr().out
    assert "Spot Mainnet" in out
    assert "Binance mainnet" in out
    assert "nothing" in out


def test_a_refused_key_prints_why_for_each_environment(capsys) -> None:
    _run("nobody-accepts")

    out = capsys.readouterr().out
    assert REFUSAL_WORDS[KeyCheckRefusal.NOT_ACCEPTED] in out
    assert REFUSED_REASON in out
    for environment in KeyEnvironment:
        assert environment.label in out


def test_a_key_that_can_withdraw_says_so_and_what_to_do(capsys) -> None:
    _run("withdrawal-enabled", as_json=True)

    body = _data(capsys)
    assert body["ok"] is False
    assert body["refusal"] == "withdrawal_enabled"
    assert body["venues"] == []
    assert "withdraw" in str(body["message"])


def test_every_refusal_has_its_words() -> None:
    assert set(REFUSAL_WORDS) == set(KeyCheckRefusal)


def test_an_unknown_format_is_a_usage_error_and_prints_nothing(capsys) -> None:
    answers, credentials, _ = _SCENARIOS["spot-testnet"]

    outcome = run_key_check(
        credentials,
        HandlerDispatcher(ScriptedProbe(answers)),
        ReportPrinter(ReportFormats.default()),
        argparse.Namespace(json=False, format="yaml"),
    )

    assert outcome is not None
    assert outcome.code is ExitCode.USAGE
    assert capsys.readouterr().out == ""
