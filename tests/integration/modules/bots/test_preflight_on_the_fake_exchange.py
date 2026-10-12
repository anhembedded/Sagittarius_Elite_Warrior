"""`EPIC-038F` — `preflight` through the composed app, against the fake exchange.

The real registry collects the checks the modules declare, the real handler runs
them, and the real adapters talk HTTP to the fake Binance server: the clock is
skewed on the exchange's side, the key is read-only or can withdraw as the
server says. Only reads are asked; the test fails if anything that places,
tests or simulates an order reaches the server.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from fake_exchange.history_log import exchange_clock_skewed_by
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IPreflightCheckTable,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.preflight_cli_handler import (
    PreflightCliHandler,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
    SPOT_MAINNET_ENV_API_KEY,
    SPOT_MAINNET_ENV_API_SECRET,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine import App

from .grid_fake_exchange import FakeExchange, app_config

EXPECTED_IDS = {
    "clock-skew",
    "credentials-present",
    "data-root-writable",
    "disk-space",
    "key-permissions",
    "no-withdraw-permission",
    "outbound-address",
    "python-floor",
}
_PLACING = ("POST", "PUT", "DELETE")
_KEY_VALUE = "mainnet-key-value"
_SIGNING_VALUE = "mainnet-signing-value"


@contextmanager
def _preflight_app(exchange: FakeExchange, venues: list[str]) -> Iterator[App]:
    config = app_config(exchange.tmp_path)
    config.load_dict({"exchange.trading_venues": venues})
    urls = exchange.urls
    with (
        patch.object(Client, "API_URL", urls.spot),
        patch.object(Client, "FUTURES_URL", urls.futures),
        patch.object(Client, "MARGIN_API_URL", urls.margin),
    ):
        engine = create_app(config)
        engine.boot()
        try:
            yield engine
        finally:
            engine.stop()


def _run(
    app: App, *, venue: str | None = None, skip: str | None = None
) -> tuple[CliOutcome | None, dict]:
    args = argparse.Namespace(venue=venue, skip=skip, json=True, format=None)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        outcome = PreflightCliHandler.handle(args, app)
    return outcome, json.loads(out.getvalue())


def _statuses(document: dict) -> dict[str, str]:
    return {check["id"]: check["status"] for check in document["data"]["checks"]}


@pytest.fixture
def mainnet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SPOT_MAINNET_ENV_API_KEY, _KEY_VALUE)
    monkeypatch.setenv(SPOT_MAINNET_ENV_API_SECRET, _SIGNING_VALUE)


def test_every_declared_check_is_in_the_report_and_nothing_is_placed(
    exchange: FakeExchange,
) -> None:
    with _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app:
        declared = {
            d.check_id
            for d in app.container.resolve(IPreflightCheckTable).descriptors()
        }  # type: ignore[type-abstract]
        outcome, document = _run(app)

    assert declared == EXPECTED_IDS
    assert set(_statuses(document)) == EXPECTED_IDS
    assert document["schema"] == "sew.preflight/1"
    assert not [r for r in exchange.urls.requests if r[0] in _PLACING]
    failed = [c for c, st in _statuses(document).items() if st == "FAIL"]
    assert failed == [] or outcome is not None, failed


def test_a_healthy_testnet_passes_the_exchange_checks(exchange: FakeExchange) -> None:
    with _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app:
        _outcome, document = _run(app)

    statuses = _statuses(document)
    assert statuses["clock-skew"] == "PASS"
    assert statuses["credentials-present"] == "PASS"
    assert statuses["key-permissions"] == "PASS"
    assert statuses["outbound-address"] == "PASS"


@pytest.mark.parametrize(("skew_ms", "expected"), [(-600, "WARN"), (-1200, "FAIL")])
def test_an_exchange_clock_off_by_600_ms_warns_and_by_1200_ms_fails(
    exchange: FakeExchange, skew_ms: int, expected: str
) -> None:
    with (
        exchange_clock_skewed_by(skew_ms),
        _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app,
    ):
        outcome, document = _run(app, skip="disk-space,data-root-writable")

    assert _statuses(document)["clock-skew"] == expected
    if expected == "FAIL":
        assert outcome is not None
        assert outcome.code is ExitCode.PREFLIGHT_FAILED


@pytest.mark.usefixtures("mainnet_key")
def test_a_read_only_mainnet_key_fails_the_permission_check_but_not_the_withdraw_check(
    exchange: FakeExchange,
) -> None:
    with _preflight_app(exchange, [TradingVenue.SPOT_MAINNET.value]) as app:
        outcome, document = _run(app)

    statuses = _statuses(document)
    assert statuses["key-permissions"] == "FAIL"
    assert statuses["no-withdraw-permission"] == "PASS"
    assert outcome is not None
    assert outcome.code is ExitCode.PREFLIGHT_FAILED


@pytest.mark.usefixtures("mainnet_key")
def test_a_withdraw_enabled_mainnet_key_fails_once_and_exits_five(
    exchange: FakeExchange,
) -> None:
    exchange.urls.api_restrictions.enable_spot_and_margin_trading = True
    exchange.urls.api_restrictions.enable_withdrawals = True
    with _preflight_app(exchange, [TradingVenue.SPOT_MAINNET.value]) as app:
        outcome, document = _run(app)

    failed = [c for c, s in _statuses(document).items() if s == "FAIL"]
    assert failed == ["no-withdraw-permission"]
    assert outcome is not None
    assert outcome.code is ExitCode.CONFIGURATION
    rendered = json.dumps(document)
    assert _KEY_VALUE not in rendered
    assert _SIGNING_VALUE not in rendered


def test_an_unknown_skip_id_is_a_usage_error(exchange: FakeExchange) -> None:
    with _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app:
        args = argparse.Namespace(
            venue=None, skip="no-such-check", json=True, format=None
        )
        outcome = PreflightCliHandler.handle(args, app)

    assert outcome is not None
    assert outcome.code is ExitCode.USAGE
    assert "no-such-check" in outcome.message


def test_a_maintenance_page_exits_six(exchange: FakeExchange) -> None:
    exchange.urls.maintenance.on = True
    with _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app:
        outcome, _document = _run(app, skip="disk-space,data-root-writable")

    assert outcome is not None
    assert outcome.code is ExitCode.EXCHANGE


def test_a_missing_key_exits_five(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(SPOT_ENV_API_KEY, raising=False)
    monkeypatch.delenv(SPOT_ENV_API_SECRET, raising=False)
    with _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app:
        outcome, document = _run(app)

    assert _statuses(document)["credentials-present"] == "FAIL"
    assert outcome is not None
    assert outcome.code is ExitCode.CONFIGURATION


def test_error_2015_from_the_exchange_prints_the_checklist_and_exits_five(
    exchange: FakeExchange,
) -> None:
    exchange.urls.keys.known = {"fake-key"}
    exchange.urls.keys.refused = {"fake-key"}
    with _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app:
        outcome, document = _run(app, skip="disk-space,data-root-writable")

    (finding,) = [
        c["findings"][0]
        for c in document["data"]["checks"]
        if c["id"] == "outbound-address"
    ]
    assert finding["status"] == "FAIL"
    assert "(1)" in finding["remedy"]
    assert "per address" in finding["remedy"]
    assert outcome is not None
    assert outcome.code is ExitCode.CONFIGURATION


def test_an_exchange_that_cannot_be_reached_exits_six(
    exchange: FakeExchange,
) -> None:
    """The route to the exchange is dead (nothing listens): the clients' own
    failure, through the real adapters, is the exchange being out of reach."""
    with (
        _preflight_app(exchange, [TradingVenue.SPOT_TESTNET.value]) as app,
        patch.object(Client, "API_TESTNET_URL", "http://127.0.0.1:9/api"),
        patch.object(Client, "API_URL", "http://127.0.0.1:9/api"),
    ):
        outcome, document = _run(app, skip="disk-space,data-root-writable")

    assert outcome is not None
    assert outcome.code is ExitCode.EXCHANGE, _statuses(document)
