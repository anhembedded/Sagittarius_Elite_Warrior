"""One group, one default severity and one label per `AlertKind`.

A table, not a method per kind: a new kind is one row, and
`test_every_alert_kind_has_one_group_and_one_default_severity` fails when the
row is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


@dataclass(frozen=True, slots=True)
class KindProfile:
    group: AlertGroup
    severity: Severity
    label: str


_CRITICAL = Severity.CRITICAL
_WARNING = Severity.WARNING
_INFO = Severity.INFO

#: The rows follow the Options wireframe (design §12.1): bot events and the
#: infrastructure row are CRITICAL, notices WARNING, routine messages INFO.
KIND_PROFILES = MappingProxyType(
    {
        AlertKind.BOT_HALTED: KindProfile(
            AlertGroup.BOT_EVENTS, _CRITICAL, "Bot halted"
        ),
        AlertKind.BOT_ERROR: KindProfile(AlertGroup.BOT_EVENTS, _CRITICAL, "Bot error"),
        AlertKind.STOP_LOSS_HIT: KindProfile(
            AlertGroup.BOT_EVENTS, _CRITICAL, "Stop loss hit"
        ),
        AlertKind.TAKE_PROFIT_HIT: KindProfile(
            AlertGroup.BOT_EVENTS, _CRITICAL, "Take profit hit"
        ),
        AlertKind.STOP_FAILED: KindProfile(
            AlertGroup.BOT_EVENTS, _CRITICAL, "Stop failed"
        ),
        AlertKind.BOT_RECOVERY_STALLED: KindProfile(
            AlertGroup.BOT_EVENTS, _WARNING, "Bot recovery stalled"
        ),
        AlertKind.BOT_AUTO_RECOVERED: KindProfile(
            AlertGroup.BOT_EVENTS, _WARNING, "Bot recovered by itself"
        ),
        AlertKind.PRICE_FEED_STALE: KindProfile(
            AlertGroup.INFRASTRUCTURE, _CRITICAL, "Price feed stale"
        ),
        AlertKind.USER_STREAM_DOWN: KindProfile(
            AlertGroup.INFRASTRUCTURE, _CRITICAL, "Account stream down"
        ),
        AlertKind.KEY_REJECTED: KindProfile(
            AlertGroup.INFRASTRUCTURE, _CRITICAL, "API key rejected"
        ),
        AlertKind.STORAGE_FAILURE: KindProfile(
            AlertGroup.INFRASTRUCTURE, _CRITICAL, "Storage failure"
        ),
        AlertKind.APP_FAILURE: KindProfile(
            AlertGroup.INFRASTRUCTURE, _CRITICAL, "Application failure"
        ),
        AlertKind.RATE_LIMITED: KindProfile(
            AlertGroup.NOTICES, _WARNING, "Rate limited"
        ),
        AlertKind.RANGE_EXIT: KindProfile(
            AlertGroup.NOTICES, _WARNING, "Price left the range"
        ),
        AlertKind.CHANNEL_FAILING: KindProfile(
            AlertGroup.NOTICES, _WARNING, "Alert channel failing"
        ),
        AlertKind.ORDER_FILLED: KindProfile(AlertGroup.ROUTINE, _INFO, "Order filled"),
        AlertKind.FILLS_SKIPPED: KindProfile(
            AlertGroup.ROUTINE, _INFO, "Fill messages skipped"
        ),
        AlertKind.HEARTBEAT: KindProfile(AlertGroup.ROUTINE, _INFO, "Heartbeat"),
        AlertKind.DAILY_SUMMARY: KindProfile(AlertGroup.ROUTINE, _INFO, "Summary"),
        AlertKind.TEST: KindProfile(AlertGroup.ROUTINE, _INFO, "Test message"),
    }
)


def group_of(kind: AlertKind) -> AlertGroup:
    return KIND_PROFILES[kind].group


def severity_of(kind: AlertKind) -> Severity:
    """The severity a source gets unless it knows better."""
    return KIND_PROFILES[kind].severity


def label_of(kind: AlertKind) -> str:
    return KIND_PROFILES[kind].label
