"""The graph `create_app()` builds delivers an alert to a channel and keeps it
across a restart (`EPIC-036A`, N2).

A test that constructs the hub proves the hub, not that the application binds,
starts and stops it (`CS-002`): this boots the real composition, with the
network boundary replaced by a fake channel declared the way a real one will be.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_hub import (
    AlertHub,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition import (
    alerting_bindings,
    channel_bindings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    AlertChannelDescriptor,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_channel import (
    FakeAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.event_bus.bus_observers import (
    IBusObserver,
    add_bus_observer,
    remove_bus_observer,
)

WAIT_S = 15.0


def _alert() -> Alert:
    return Alert.raised(
        AlertKind.APP_FAILURE,
        AlertSubject.app(),
        "Something failed",
        "detail",
        datetime.now(UTC),
        "integration",
    )


@pytest.fixture(autouse=True)
def _data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    return tmp_path


def _declare(monkeypatch: pytest.MonkeyPatch, channel: FakeAlertChannel) -> None:
    monkeypatch.setattr(
        channel_bindings,
        "CHANNEL_DESCRIPTORS",
        (AlertChannelDescriptor("phone", lambda _resolver: channel),),
    )


@pytest.fixture
def booted(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[App, FakeAlertChannel]]:
    channel = FakeAlertChannel()
    _declare(monkeypatch, channel)
    app = create_app(ConfigManager())
    app.boot()
    try:
        yield app, channel
    finally:
        app.stop()


def test_a_published_alert_reaches_a_declared_channel(
    booted: tuple[App, FakeAlertChannel],
) -> None:
    app, channel = booted

    app.container.resolve(IAlertPublisher).publish(_alert())  # type: ignore[type-abstract]

    assert channel.done.wait(WAIT_S)
    assert [r.alert.kind for r in channel.received] == [AlertKind.APP_FAILURE]


def test_an_undelivered_alert_is_sent_after_a_restart(
    monkeypatch: pytest.MonkeyPatch, _data_root: Path
) -> None:
    down = FakeAlertChannel(default=DeliveryResult.failed("network down"))
    _declare(monkeypatch, down)
    first = create_app(ConfigManager())
    first.boot()
    try:
        first.container.resolve(IAlertPublisher).publish(_alert())  # type: ignore[type-abstract]
        assert down.done.wait(WAIT_S)
    finally:
        first.stop()
    assert (_data_root / "state" / "alerts.sqlite3").is_file()

    back = FakeAlertChannel()
    _declare(monkeypatch, back)
    second = create_app(ConfigManager())
    second.boot()
    try:
        assert back.done.wait(WAIT_S)
    finally:
        second.stop()

    assert [r.alert.kind for r in back.received] == [AlertKind.APP_FAILURE]


def test_stopping_the_app_leaves_no_alerting_thread(
    booted: tuple[App, FakeAlertChannel],
) -> None:
    app, _channel = booted

    app.stop()

    assert not [t for t in threading.enumerate() if t.name.startswith("alerting-")]


def test_the_snapshot_carries_an_alerting_section(
    booted: tuple[App, FakeAlertChannel], _data_root: Path
) -> None:
    snapshot = FileHealthSnapshotSource(_data_root / "state" / "health.json").read()

    assert snapshot is not None
    assert snapshot.sections["alerting"]["undelivered"] == 0
    assert "alerting" not in snapshot.unavailable_sections


def test_a_read_only_copy_neither_writes_the_outbox_nor_starts_a_lane(
    monkeypatch: pytest.MonkeyPatch, _data_root: Path
) -> None:
    channel = FakeAlertChannel()
    _declare(monkeypatch, channel)
    lock = _data_root / "state" / "instance.lock"
    first = InstanceAccess.acquire(lock)
    second = InstanceAccess.acquire(lock)
    assert second.read_only is True

    app = create_app(ConfigManager(), second)
    app.boot()
    try:
        app.container.resolve(IAlertPublisher).publish(_alert())  # type: ignore[type-abstract]
        assert not [t for t in threading.enumerate() if t.name.startswith("alerting-")]
    finally:
        app.stop()
        first.release()

    assert not (_data_root / "state" / "alerts.sqlite3").exists()
    assert channel.received == []


class _EventNames(IBusObserver):
    def __init__(self) -> None:
        self.names: list[str] = []

    def event_emitted(self, event_name: str, handler_count: int) -> None:
        self.names.append(event_name)


def test_the_periodic_flush_puts_nothing_on_the_event_bus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Developer mode's event log lists every bus event (`EPIC-033P`). A
    one-second `Scheduler` job published `runtime.tasks.started` / `.completed`
    twice a second and widened that log's column past the conformance rule."""
    flushed = threading.Event()
    calls: list[int] = []
    real = AlertHub.flush_due

    def counting(self: AlertHub) -> None:
        real(self)
        calls.append(1)
        if len(calls) >= 3:
            flushed.set()

    monkeypatch.setattr(AlertHub, "flush_due", counting)
    monkeypatch.setattr(alerting_bindings, "HOUSEKEEPING_SECONDS", 0.01)
    observer = _EventNames()
    add_bus_observer(observer)
    app = create_app(ConfigManager())
    try:
        app.boot()
        assert flushed.wait(WAIT_S)
    finally:
        app.stop()
        remove_bus_observer(observer)

    assert [n for n in observer.names if n.startswith("runtime.tasks.")] == []
