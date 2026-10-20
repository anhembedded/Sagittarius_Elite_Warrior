"""`EPIC-036B` — a failure of the app reaches the alert module and the in-app toast.

`SystemFailureRelay` replaces `NotificationEventHandler` (`BOT-018`): it hears the Qt-free
failure sources, hands each to the alerting module's `ISystemFailureReporter` and to the
window's toast. Like `test_system_failure_log.py`, the first test boots the real object graph
(`BUG-126`: a subscriber only a unit test constructs proves nothing about production).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_system_failure_reporter import (
    ISystemFailureReporter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.shell.system_failure_relay import (
    SystemFailureRelay,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.failure_doubles import (
    RecordingChannel,
    RecordingLogger,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.runtime.tasks.events import TaskFailed

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "src",
    "config",
)
_SRC = Path(__file__).resolve().parents[3] / "src"


class _RecordingReporter(ISystemFailureReporter):
    def __init__(self) -> None:
        self.reports: list[tuple[str, str]] = []

    def report_failure(self, source: str, summary: str) -> None:
        self.reports.append((source, summary))


class _RaisingReporter(ISystemFailureReporter):
    def report_failure(self, source: str, summary: str) -> None:
        raise RuntimeError("the alert module is down")


class _RaisingChannel(INotificationChannel):
    def send(self, message: str) -> None:
        raise RuntimeError("channel is down")


def _relay(
    reporter: ISystemFailureReporter | None,
) -> tuple[SystemFailureRelay, MemoryEventBus, RecordingChannel, RecordingLogger]:
    bus = MemoryEventBus()
    logger = RecordingLogger()
    relay = SystemFailureRelay(bus, lambda: reporter, logger)
    toast = RecordingChannel()
    relay.add_channel(toast)
    return relay, bus, toast, logger


def _failed_task() -> TaskFailed:
    return TaskFailed(
        task_id="task-7",
        task_name="historical-sync",
        error=ValueError("candle grid drifted"),
    )


@pytest.fixture
def booted_app():
    config_manager = ConfigManager()
    config_manager.load_json(os.path.join(_CONFIG_DIR, "app_config.json"))
    config_manager.load_json(os.path.join(_CONFIG_DIR, "user_config.json"))
    app = create_app(config_manager)
    yield app
    app.stop()


def test_the_real_graph_relays_both_failure_sources_to_the_alert_module(booted_app):
    bus = booted_app.event_bus
    assert isinstance(bus, MemoryEventBus)

    unheard = [
        event_type.__name__
        for event_type in (BulkSyncProgressEvent, TaskFailed)
        if not bus.get_handlers(event_type)
    ]

    assert unheard == [], f"{unheard} reach no subscriber after create_app()"
    assert ISystemFailureReporter in booted_app.container.registrations(), (
        "the alerting module binds no ISystemFailureReporter, so the relay has nowhere to send"
    )


def test_a_failed_task_reaches_the_alert_module_and_the_toast() -> None:
    reporter = _RecordingReporter()
    _, bus, toast, _ = _relay(reporter)

    bus.emit(_failed_task())

    expected = "Background task 'historical-sync' (id task-7) failed: ValueError: candle grid drifted"
    assert reporter.reports == [("historical-sync", expected)]
    assert toast.sent == [expected]


def test_a_sync_error_reaches_the_alert_module_and_the_toast() -> None:
    reporter = _RecordingReporter()
    _, bus, toast, _ = _relay(reporter)

    bus.emit(
        BulkSyncProgressEvent(
            current_index=3,
            total_targets=10,
            symbol="ETHUSDT",
            interval="1m",
            has_error=True,
            message="Failed: connection reset",
        )
    )

    [(source, summary)] = reporter.reports
    assert "ETHUSDT" in source
    assert "ETHUSDT" in summary
    assert "connection reset" in summary
    assert toast.sent == [summary]


def test_a_successful_sync_step_reports_nothing() -> None:
    reporter = _RecordingReporter()
    _, bus, toast, _ = _relay(reporter)

    bus.emit(
        BulkSyncProgressEvent(
            current_index=1,
            total_targets=10,
            symbol="ETHUSDT",
            interval="1m",
            has_error=False,
            message="[1/10] ETHUSDT (1m) complete.",
        )
    )

    assert reporter.reports == []
    assert toast.sent == []


def test_a_raising_alert_module_does_not_stop_the_toast_or_the_publisher() -> None:
    _, bus, toast, logger = _relay(_RaisingReporter())

    bus.emit(_failed_task())

    assert len(toast.sent) == 1
    assert any("historical-sync" in line for line in logger.lines.get("warning", []))


def test_a_process_without_the_alert_module_still_toasts() -> None:
    _, bus, toast, _ = _relay(None)

    bus.emit(_failed_task())

    assert len(toast.sent) == 1


def test_a_raising_toast_does_not_stop_the_alert_module() -> None:
    reporter = _RecordingReporter()
    relay, bus, _, logger = _relay(reporter)
    relay.add_channel(_RaisingChannel())

    bus.emit(_failed_task())

    assert len(reporter.reports) == 1
    assert any("_RaisingChannel" in line for line in logger.lines.get("warning", []))


def test_the_old_handler_and_its_telegram_wiring_are_gone() -> None:
    assert not (_SRC / "shell" / "notification_event_handler.py").exists()
    composition = (_SRC / "shell" / "composition_root.py").read_text(encoding="utf-8")
    for retired in ("NotificationEventHandler", "TelegramNotificationChannel"):
        assert retired not in composition
