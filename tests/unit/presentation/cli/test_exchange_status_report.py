"""`exchange-status` as a report: pinned field names, exit codes, and the command (`EPIC-038B`)."""

from __future__ import annotations

import argparse
import json
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_exit_code import (
    EXIT_CODE_FOR_FAILURE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_cmd import (
    execute_exchange_status,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_report import (
    exchange_status_outcome,
    exchange_status_report,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.presentation.cli.golden_cases import (
    EXCHANGE_STATUS_CASES,
)
from sagittarius_engine import App

#: `sew.exchange-status/1`. Adding a field adds a name here in the same commit;
#: renaming or removing one is a new schema version, so this set changing without
#: `SCHEMA_VERSION` changing is the review's cue.
_PINNED_FIELDS = {
    "venue",
    "reachable",
    "failure",
    "server_time_skew_ms",
    "clock_skew_within_recv_window",
    "usdt_balance",
    "available_balance",
    "unrealized_pnl",
    "asset_mode",
    "position_mode",
    "margin_type",
    "open_position_count",
    "equity",
    "holdings",
    "can_trade",
}
_PINNED_HOLDING_FIELDS = {"asset", "free", "locked", "is_dust"}


@pytest.mark.parametrize("name", sorted(EXCHANGE_STATUS_CASES))
def test_exchange_status_json_has_the_pinned_fields(name: str) -> None:
    report = exchange_status_report(EXCHANGE_STATUS_CASES[name])

    assert set(report.payload) == _PINNED_FIELDS
    assert report.schema == "sew.exchange-status/1"


def test_holdings_carry_the_pinned_fields() -> None:
    report = exchange_status_report(EXCHANGE_STATUS_CASES["spot_success_with_holdings"])

    holdings = report.payload["holdings"]
    assert isinstance(holdings, list)
    assert holdings
    assert all(set(holding) == _PINNED_HOLDING_FIELDS for holding in holdings)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", sorted(EXCHANGE_STATUS_CASES))
def test_every_payload_is_plain_json(name: str) -> None:
    """No `Decimal`, enum or datetime in a payload: `json.dumps` with no
    fallback is the proof, and money is a string, never a float."""
    payload = exchange_status_report(EXCHANGE_STATUS_CASES[name]).payload

    assert json.loads(json.dumps(payload)) == payload


def test_the_json_view_states_what_the_text_view_says() -> None:
    """One status, two views, no disagreement: the figures in the text are the
    payload's."""
    report = exchange_status_report(
        EXCHANGE_STATUS_CASES["futures_success_single_asset"]
    )

    assert report.payload["usdt_balance"] == "15000.00"
    assert report.payload["available_balance"] == "12345.67"
    assert report.payload["unrealized_pnl"] == "-100.5"
    assert report.payload["open_position_count"] == 2
    assert report.payload["clock_skew_within_recv_window"] is True


def test_a_skew_beyond_the_recv_window_is_not_within_it() -> None:
    report = exchange_status_report(
        EXCHANGE_STATUS_CASES["futures_skew_beyond_recv_window"]
    )

    assert report.payload["clock_skew_within_recv_window"] is False


def test_every_failure_kind_has_an_exit_code() -> None:
    assert set(EXIT_CODE_FOR_FAILURE) == set(ConnectionFailureKind)


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        (ConnectionFailureKind.NOT_CONFIGURED, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.WITHDRAWAL_ENABLED, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.KEY_REJECTED, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.CLOCK_SKEW, ExitCode.EXCHANGE),
        (ConnectionFailureKind.BAD_SIGNATURE, ExitCode.CONFIGURATION),
        (ConnectionFailureKind.NETWORK, ExitCode.EXCHANGE),
        (ConnectionFailureKind.MAINTENANCE, ExitCode.EXCHANGE),
    ],
)
def test_a_failed_connection_exits_with_the_documented_code(
    kind: ConnectionFailureKind, code: ExitCode
) -> None:
    """DESIGN §7 / D9: 5 when only the operator can fix it (no key, `-2015`,
    `-1022`, a key that can withdraw), 6 when a restart can outlast it (network,
    maintenance, `-1021`)."""
    status = EXCHANGE_STATUS_CASES[f"futures_{kind.name.lower()}"]

    assert exchange_status_outcome(status) == CliOutcome(code)


def test_a_healthy_connection_exits_zero() -> None:
    status = EXCHANGE_STATUS_CASES["futures_success_without_summary"]

    assert exchange_status_outcome(status) is None


def _app(status: ExchangeConnectionStatus) -> Mock:
    snapshot = FakeAccountSnapshot(status)
    app = Mock(spec=App)
    app.container.resolve.side_effect = lambda port: {
        IAccountSnapshot: snapshot,
        IReportFormats: ReportFormats.default(),
    }[port]
    return app


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json": False, "format": None, **values})


def test_the_command_prints_the_text_report_and_succeeds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = EXCHANGE_STATUS_CASES["futures_success_without_summary"]

    outcome = execute_exchange_status(_app(status), _args())

    assert outcome is None
    assert "Connection: ✔" in capsys.readouterr().out


def test_a_failed_connection_prints_its_json_and_then_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = EXCHANGE_STATUS_CASES["futures_key_rejected"]

    outcome = execute_exchange_status(_app(status), _args(json=True))

    assert outcome == CliOutcome(ExitCode.CONFIGURATION)
    assert json.loads(capsys.readouterr().out)["data"]["failure"] == "key_rejected"


def test_an_unknown_format_is_a_usage_error_not_the_connections_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = EXCHANGE_STATUS_CASES["futures_key_rejected"]

    outcome = execute_exchange_status(_app(status), _args(format="yaml"))

    assert outcome is not None
    assert outcome.code is ExitCode.USAGE
    assert capsys.readouterr().out == ""
