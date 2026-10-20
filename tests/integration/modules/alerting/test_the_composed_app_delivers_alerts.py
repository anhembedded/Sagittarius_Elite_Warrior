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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
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


class _KindChannel(FakeAlertChannel):
    """A fake channel that also says when an alert of a given kind has been delivered, so a
    test waits for the alert it published and not for whichever one arrives first: the booted
    app sends a heartbeat of its own on its first housekeeping pass (`EPIC-036E`)."""

    def __init__(self, default: DeliveryResult | None = None) -> None:
        super().__init__(default=default)
        self._lock = threading.Lock()
        self._delivered: dict[AlertKind, threading.Event] = {}

    def delivered(self, kind: AlertKind) -> threading.Event:
        with self._lock:
            return self._delivered.setdefault(kind, threading.Event())

    def deliver(self, alert: Alert, loudness: Loudness) -> DeliveryResult:
        try:
            return super().deliver(alert, loudness)
        finally:
            self.delivered(alert.kind).set()


def _kinds(channel: FakeAlertChannel) -> list[AlertKind]:
    """What the channel received, without the heartbeat the booted app sends on its own
    schedule (`EPIC-036E`): these tests are about the alert they publish."""
    return [
        r.alert.kind
        for r in channel.received
        if r.alert.kind is not AlertKind.HEARTBEAT
    ]


def _alerting_threads() -> frozenset[threading.Thread]:
    return frozenset(t for t in threading.enumerate() if t.name.startswith("alerting-"))


@pytest.fixture
def threads_before() -> frozenset[threading.Thread]:
    """The alerting threads of other apps still alive in this process (the
    sanity tier keeps one booted for its whole session): a test asks what *its*
    app left, not whether the process has none."""
    return _alerting_threads()


@pytest.fixture
def booted(
    monkeypatch: pytest.MonkeyPatch, threads_before: frozenset[threading.Thread]
) -> Iterator[tuple[App, _KindChannel]]:
    channel = _KindChannel()
    _declare(monkeypatch, channel)
    app = create_app(ConfigManager())
    app.boot()
    try:
        yield app, channel
    finally:
        app.stop()


def test_a_published_alert_reaches_a_declared_channel(
    booted: tuple[App, _KindChannel],
) -> None:
    app, channel = booted

    app.container.resolve(IAlertPublisher).publish(_alert())  # type: ignore[type-abstract]

    assert channel.delivered(AlertKind.APP_FAILURE).wait(WAIT_S)
    assert _kinds(channel) == [AlertKind.APP_FAILURE]


def test_an_undelivered_alert_is_sent_after_a_restart(
    monkeypatch: pytest.MonkeyPatch, _data_root: Path
) -> None:
    down = _KindChannel(default=DeliveryResult.failed("network down"))
    _declare(monkeypatch, down)
    first = create_app(ConfigManager())
    first.boot()
    try:
        first.container.resolve(IAlertPublisher).publish(_alert())  # type: ignore[type-abstract]
        assert down.delivered(AlertKind.APP_FAILURE).wait(WAIT_S)
    finally:
        first.stop()
    assert (_data_root / "state" / "alerts.sqlite3").is_file()

    back = _KindChannel()
    _declare(monkeypatch, back)
    second = create_app(ConfigManager())
    second.boot()
    try:
        assert back.delivered(AlertKind.APP_FAILURE).wait(WAIT_S)
    finally:
        second.stop()

    assert _kinds(back) == [AlertKind.APP_FAILURE]


def test_stopping_the_app_leaves_no_alerting_thread(
    booted: tuple[App, _KindChannel],
    threads_before: frozenset[threading.Thread],
) -> None:
    app, _channel = booted
    assert _alerting_threads() - threads_before  # it started some

    app.stop()

    assert _alerting_threads() - threads_before == frozenset()


def test_the_snapshot_carries_an_alerting_section(
    booted: tuple[App, _KindChannel], _data_root: Path
) -> None:
    snapshot = FileHealthSnapshotSource(_data_root / "state" / "health.json").read()

    assert snapshot is not None
    assert snapshot.sections["alerting"]["undelivered"] == 0
    assert "alerting" not in snapshot.unavailable_sections


def test_a_read_only_copy_neither_writes_the_outbox_nor_starts_a_lane(
    monkeypatch: pytest.MonkeyPatch,
    _data_root: Path,
    threads_before: frozenset[threading.Thread],
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
        assert _alerting_threads() - threads_before == frozenset()
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
