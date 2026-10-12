"""`EPIC-038F` — credentials, key permissions, withdraw, and the `-2015` checklist."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_report import (
    preflight_report,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.clock_skew_check import (
    ClockSkewCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.credentials_present_check import (
    CredentialsPresentCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.key_permissions_check import (
    KeyPermissionsCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.no_withdraw_permission_check import (
    NoWithdrawPermissionCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.outbound_address_check import (
    CHECKLIST,
    OutboundAddressCheck,
    address_in,
    describe_address,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_credentials_provider import (
    FakeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.json_report_renderer import (
    JsonReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)

from .preflight_world import (
    KEY,
    SIGNING_PHRASE,
    ArrangedProbe,
    StoredKey,
    accepted,
    reads_over,
    status,
    venue,
)

SPOT_MAIN = TradingVenue.SPOT_MAINNET
FUT_MAIN = TradingVenue.FUTURES_MAINNET
SPOT_TEST = TradingVenue.SPOT_TESTNET


def _on_mainnet(
    check_type, verdict: EnvironmentVerdict | None, which=SPOT_MAIN
) -> CheckResult:
    reads = reads_over(venue(which), probe=ArrangedProbe(verdict))
    return check_type(reads).run(PreflightScope())


def test_a_withdraw_enabled_key_fails() -> None:
    result = _on_mainnet(NoWithdrawPermissionCheck, accepted(withdraw=True))

    assert result.status is CheckStatus.FAIL
    assert "key without withdrawal" in result.findings[0].remedy
    assert result.cause is CheckCause.CONFIGURATION, "a restart cannot fix it: exit 5"


def test_a_key_that_cannot_withdraw_passes() -> None:
    assert _on_mainnet(NoWithdrawPermissionCheck, accepted()).status is CheckStatus.PASS


def test_a_testnet_key_cannot_withdraw_and_the_check_says_why() -> None:
    reads = reads_over(venue(SPOT_TEST))

    result = NoWithdrawPermissionCheck(reads).run(PreflightScope())

    assert result.status is CheckStatus.PASS
    assert "testnet has no withdrawal permission" in result.findings[0].reason


@pytest.mark.parametrize(
    ("which", "verdict", "expected"),
    [
        (SPOT_MAIN, accepted(trade_spot=True, trade_futures=False), CheckStatus.PASS),
        (SPOT_MAIN, accepted(trade_spot=False, trade_futures=True), CheckStatus.FAIL),
        (FUT_MAIN, accepted(trade_spot=False, trade_futures=True), CheckStatus.PASS),
        (FUT_MAIN, accepted(trade_spot=True, trade_futures=False), CheckStatus.FAIL),
        (SPOT_MAIN, accepted(trade_spot=False, trade_futures=False), CheckStatus.FAIL),
    ],
)
def test_a_trading_venue_needs_the_permission_for_its_own_market(
    which: TradingVenue, verdict: EnvironmentVerdict, expected: CheckStatus
) -> None:
    assert _on_mainnet(KeyPermissionsCheck, verdict, which).status is expected


def test_a_read_only_key_fails_on_a_trading_venue() -> None:
    result = _on_mainnet(
        KeyPermissionsCheck, accepted(trade_spot=False, trade_futures=False)
    )

    assert "read-only" in result.findings[0].reason


def test_a_testnet_is_judged_by_the_accounts_can_trade_flag() -> None:
    def run(flag: bool | None) -> CheckStatus:
        reads = reads_over(venue(SPOT_TEST, status(SPOT_TEST, can_trade=flag)))
        return KeyPermissionsCheck(reads).run(PreflightScope()).status

    assert (run(True), run(False), run(None)) == (
        CheckStatus.PASS,
        CheckStatus.FAIL,
        CheckStatus.WARN,
    )


def test_the_permission_list_is_read_once_for_both_permission_checks() -> None:
    probe = ArrangedProbe(accepted())
    reads = reads_over(venue(SPOT_MAIN), probe=probe)
    scope = PreflightScope()

    KeyPermissionsCheck(reads).run(scope)
    NoWithdrawPermissionCheck(reads).run(scope)

    assert probe.asked == 1


@pytest.mark.parametrize("standing", [KeyStanding.UNKNOWN, KeyStanding.REFUSED])
def test_a_key_the_exchange_refuses_is_a_credentials_failure(
    standing: KeyStanding,
) -> None:
    verdict = EnvironmentVerdict(
        KeyEnvironment.MAINNET, standing, reason="-2015 Invalid API-key"
    )

    result = _on_mainnet(KeyPermissionsCheck, verdict)

    assert result.cause is CheckCause.CONFIGURATION


def test_an_unreachable_exchange_is_not_a_key_failure() -> None:
    verdict = EnvironmentVerdict(
        KeyEnvironment.MAINNET,
        KeyStanding.UNREACHABLE,
        failure=ConnectionFailureKind.NETWORK,
    )

    assert _on_mainnet(NoWithdrawPermissionCheck, verdict).cause is CheckCause.EXCHANGE


def test_with_no_key_the_permissions_are_a_warning_and_the_exchange_is_not_asked() -> (
    None
):
    probe = ArrangedProbe()
    reads = reads_over(
        venue(SPOT_MAIN, credentials=FakeCredentialsProvider(has_key=False)),
        probe=probe,
    )

    result = KeyPermissionsCheck(reads).run(PreflightScope())

    assert result.status is CheckStatus.WARN
    assert probe.asked == 0


@pytest.mark.parametrize(
    "source", [CredentialsSource.ENV, CredentialsSource.FILE, CredentialsSource.KEYRING]
)
def test_the_credentials_check_names_the_source_and_never_the_value(
    source: CredentialsSource,
) -> None:
    reads = reads_over(venue(SPOT_TEST, credentials=StoredKey(source)))

    result = CredentialsPresentCheck(reads).run(PreflightScope())

    assert result.status is CheckStatus.PASS
    assert source.value in result.findings[0].reason


def test_an_absent_key_is_a_credentials_failure() -> None:
    reads = reads_over(
        venue(SPOT_TEST, credentials=FakeCredentialsProvider(has_key=False))
    )

    result = CredentialsPresentCheck(reads).run(PreflightScope())

    assert result.status is CheckStatus.FAIL
    assert result.cause is CheckCause.CONFIGURATION


def test_a_withdraw_enabled_key_is_one_failure_not_four() -> None:
    """The venue's account reader is key-gated in production, so a key that can
    withdraw reads as `WITHDRAWAL_ENABLED` there; the stored key is still present."""
    gated = status(
        SPOT_MAIN, skew_ms=None, failure=ConnectionFailureKind.WITHDRAWAL_ENABLED
    )
    reads = reads_over(
        venue(SPOT_MAIN, gated, StoredKey(CredentialsSource.KEYRING)),
        probe=ArrangedProbe(accepted(withdraw=True)),
    )
    scope = PreflightScope()
    checks = (
        CredentialsPresentCheck,
        ClockSkewCheck,
        OutboundAddressCheck,
        KeyPermissionsCheck,
        NoWithdrawPermissionCheck,
    )

    results = [c(reads).run(scope) for c in checks]

    assert [r.check_id for r in results if r.status is CheckStatus.FAIL] == [
        "no-withdraw-permission"
    ]


def test_error_2015_prints_the_three_cause_checklist() -> None:
    rejected = status(SPOT_TEST, skew_ms=10, failure=ConnectionFailureKind.KEY_REJECTED)
    reads = reads_over(venue(SPOT_TEST, rejected))

    result = OutboundAddressCheck(reads).run(PreflightScope())

    finding = result.findings[0]
    assert result.status is CheckStatus.FAIL
    assert result.cause is CheckCause.CONFIGURATION
    assert finding.remedy == CHECKLIST
    for cause in ("(1)", "(2)", "(3)", "per address", "IPv6"):
        assert cause in finding.remedy
    assert "-2015" in finding.reason


def test_the_address_the_exchange_named_is_reported_with_its_family() -> None:
    reply = (
        "-2015 Invalid API-key, IP, or permissions for action, request ip: 203.0.113.9."
    )
    verdict = EnvironmentVerdict(
        KeyEnvironment.MAINNET, KeyStanding.REFUSED, reason=reply
    )
    rejected = status(SPOT_MAIN, skew_ms=10, failure=ConnectionFailureKind.KEY_REJECTED)
    reads = reads_over(venue(SPOT_MAIN, rejected), probe=ArrangedProbe(verdict))

    result = OutboundAddressCheck(reads).run(PreflightScope())

    assert "203.0.113.9 (IPv4)" in result.findings[0].reason


@pytest.mark.parametrize(
    ("reply", "address"),
    [
        ("request ip: 2001:db8::1", "2001:db8::1"),
        ("Request IP: 198.51.100.7", "198.51.100.7"),
        ("no address in this one", None),
        ("request ip: 999.1.1.1", None),
    ],
)
def test_the_address_is_read_from_the_reply_or_honestly_absent(
    reply: str, address: str | None
) -> None:
    assert address_in(reply) == address


def test_an_address_the_exchange_did_not_report_is_said_to_be_unknown() -> None:
    assert "did not report" in describe_address(None)
    assert "IPv6" in describe_address("2001:db8::1")


def test_an_accepted_key_means_this_address_is_allowed() -> None:
    reads = reads_over(venue(SPOT_TEST))

    assert OutboundAddressCheck(reads).run(PreflightScope()).status is CheckStatus.PASS


def test_no_secret_value_appears_in_the_report() -> None:
    """Every trading check ran against a provider whose key and secret are known;
    neither may be in the rendered text, the JSON, or any finding."""
    reads = reads_over(
        venue(SPOT_MAIN, credentials=StoredKey(CredentialsSource.KEYRING)),
        venue(SPOT_TEST, credentials=StoredKey(CredentialsSource.ENV)),
        probe=ArrangedProbe(accepted(withdraw=True)),
    )
    scope = PreflightScope()
    checks = (
        ClockSkewCheck,
        CredentialsPresentCheck,
        KeyPermissionsCheck,
        NoWithdrawPermissionCheck,
        OutboundAddressCheck,
    )
    results = tuple(c(reads).run(scope) for c in checks)
    report = preflight_report(results)

    rendered = TextReportRenderer().render(report) + JsonReportRenderer().render(report)

    assert KEY not in rendered
    assert SIGNING_PHRASE not in rendered
    assert (
        json.loads(JsonReportRenderer().render(report))["data"]["summary"]["fail"] >= 1
    )


def test_with_no_key_anywhere_the_exchange_checks_warn_and_the_credentials_check_fails() -> (
    None
):
    reads = reads_over(
        venue(SPOT_TEST, credentials=FakeCredentialsProvider(has_key=False)),
        venue(SPOT_MAIN, credentials=FakeCredentialsProvider(has_key=False)),
    )
    scope = PreflightScope()

    skew = ClockSkewCheck(reads).run(scope)
    credentials = CredentialsPresentCheck(reads).run(scope)

    assert skew.status is CheckStatus.WARN
    assert "--venue" in skew.findings[0].remedy
    assert credentials.status is CheckStatus.FAIL
    assert credentials.cause is CheckCause.CONFIGURATION


def test_only_venues_with_a_key_are_checked_unless_one_is_named() -> None:
    reads = reads_over(
        venue(SPOT_TEST),
        venue(
            SPOT_MAIN,
            status(
                SPOT_MAIN, skew_ms=None, failure=ConnectionFailureKind.NOT_CONFIGURED
            ),
            FakeCredentialsProvider(has_key=False),
        ),
    )

    by_default = ClockSkewCheck(reads).run(PreflightScope())
    named = ClockSkewCheck(reads).run(PreflightScope(venue="spot_mainnet"))

    assert [f.subject for f in by_default.findings] == ["spot_testnet"]
    assert [f.subject for f in named.findings] == ["spot_mainnet"]
    assert named.status is CheckStatus.WARN, (
        "a named venue with no key was not measured"
    )


def test_a_named_venue_the_build_does_not_serve_is_a_failure() -> None:
    reads = reads_over(venue(SPOT_TEST))

    result = ClockSkewCheck(reads).run(PreflightScope(venue="futures_mainnet"))

    assert result.status is CheckStatus.FAIL
    assert "not served" in result.findings[0].reason


@pytest.mark.parametrize(
    "kind",
    [
        ConnectionFailureKind.BAD_SIGNATURE,
        ConnectionFailureKind.CLOCK_SKEW,
        ConnectionFailureKind.NETWORK,
        ConnectionFailureKind.MAINTENANCE,
    ],
)
def test_a_signed_read_that_failed_after_the_time_call_is_never_a_pass(
    kind: ConnectionFailureKind,
) -> None:
    """Both readers set the skew after the unsigned `/time` and before the signed
    account read, so the skew is known while the key was never accepted."""
    failed = status(SPOT_TEST, skew_ms=40, failure=kind)
    reads = reads_over(venue(SPOT_TEST, failed))

    result = OutboundAddressCheck(reads).run(PreflightScope())

    assert result.status is not CheckStatus.PASS
    assert "accepted the key" not in result.findings[0].reason
