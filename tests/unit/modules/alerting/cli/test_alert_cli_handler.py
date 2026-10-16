"""`EPIC-036G` — `alert test` sends one loud test message per configured channel,
reports each answer, and exits by the worst one."""

from __future__ import annotations

import argparse

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
    ChannelTestOutcome,
    SendTestMessage,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.cli.alert_cli_handler import (
    AlertCliHandler,
    outcome_of,
    send_test_report,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


def test_the_send_test_reaches_every_channel_loudly_as_info() -> None:
    phone, backup = FakeAlertChannel(), FakeAlertChannel()
    catalog = RegisteredChannelCatalog({"phone": phone, "backup": backup})

    outcomes = SendTestMessage(catalog, FakeAlertClock()).run()

    assert [o.channel_id for o in outcomes] == ["phone", "backup"]
    for channel in (phone, backup):
        [received] = channel.received
        assert received.alert.kind is AlertKind.TEST
        assert received.alert.severity is Severity.INFO
        assert received.loudness is Loudness.LOUD


def test_no_channel_means_no_outcome() -> None:
    assert SendTestMessage(RegisteredChannelCatalog({}), FakeAlertClock()).run() == ()


def test_the_report_names_each_channel_and_why_one_was_not_sent() -> None:
    report = send_test_report(
        (
            ChannelTestOutcome("discord", DeliveryResult.sent()),
            ChannelTestOutcome(
                "backup", DeliveryResult.refused("Discord refused (404)")
            ),
        )
    )

    assert report.schema == "sew.alert/1"
    assert report.payload == {
        "channels": [
            {"channel": "discord", "sent": True, "reason": ""},
            {"channel": "backup", "sent": False, "reason": "Discord refused (404)"},
        ]
    }


@pytest.mark.parametrize(
    "results, code",
    [
        ((DeliveryResult.sent(),), None),
        ((DeliveryResult.sent(), DeliveryResult.failed("timed out")), ExitCode.ERROR),
        (
            (DeliveryResult.failed("timed out"), DeliveryResult.refused("404")),
            ExitCode.CONFIGURATION,
        ),
    ],
)
def test_the_exit_status_is_the_worst_answer(
    results: tuple[DeliveryResult, ...], code: ExitCode | None
) -> None:
    outcome = outcome_of(
        tuple(ChannelTestOutcome(str(n), r) for n, r in enumerate(results))
    )

    assert (None if outcome is None else outcome.code) == code


def test_an_unknown_action_is_a_usage_error() -> None:
    outcome = AlertCliHandler.handle(argparse.Namespace(action="nope"), app=None)  # type: ignore[arg-type]

    assert outcome is not None and outcome.code is ExitCode.USAGE
