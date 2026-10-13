"""`RunCommand` on the graph `create_app()` builds (`EPIC-038D`).

The unit tests construct the host from doubles, and so prove nothing about wiring
(`CS-002`): this builds the real application - the bots module with its store, the
operations module with its snapshot and cadence, the trading module with its probe -
and runs the command against it. Only the signal is by hand (the source is the port's
double); the process-level proof with real signals is `test_run_process.py`.

Nothing here reaches an exchange: no key, no bot to start.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_health_snapshot_source import (
    FileHealthSnapshotSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    health_lines_in,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_command import (
    RunCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_options import (
    HostSignalName,
    RunOptions,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_signal_source import (
    IShutdownSignalSource,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine import App

from ..bots.grid_fake_exchange import app_config


class _Source(IShutdownSignalSource):
    """A signal source the test fires by hand."""

    def __init__(self) -> None:
        self.installed = False
        self.restored = 0
        self._on_signal: Callable[[], None] | None = None

    def install(self, on_signal: Callable[[], None]) -> None:
        self.installed = True
        self._on_signal = on_signal

    def restore(self) -> None:
        self.restored += 1

    def fire(self) -> None:
        assert self._on_signal is not None
        self._on_signal()


class _Plan(IBotPlan):
    def __init__(self, *bot_ids: str) -> None:
        self._ids = frozenset(bot_ids)

    def exists(self) -> bool:
        return True

    def wants_running(self) -> frozenset[str]:
        return self._ids


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(f"{record.name} - {record.levelname} - {record.getMessage()}")


@contextmanager
def _heard() -> Iterator[list[str]]:
    """What `App.Operations` said; the composed app turns propagation off, so `caplog` sees none."""
    handler = _Lines()
    logger = logging.getLogger("App.Operations")
    logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    return tmp_path


def _app(data_root: Path) -> App:
    return create_app(app_config(data_root))


def _seed_mainnet_bot(data_root: Path, bot_id: str) -> None:
    JsonBotStore(data_root / "bots").save(
        StoredBot(
            Bot(
                BotId(bot_id),
                BotDefinition(
                    "real money",
                    "grid",
                    TradingVenue.SPOT_MAINNET,
                    "BTCUSDT",
                    {"lower": "1"},
                ),
                BotLifecycle(BotLifecycleState.STOPPED),
                datetime(2026, 10, 1, tzinfo=UTC),
            )
        )
    )


def test_an_unconfirmed_mainnet_start_planned_is_refused_with_two_and_nothing_boots(
    data_root: Path,
) -> None:
    _seed_mainnet_bot(data_root, "aaaaaa")
    app = _app(data_root)
    app.container.singleton(IBotPlan, _Plan("aaaaaa"))  # type: ignore[type-abstract]
    source = _Source()

    outcome = RunCommand(
        app, RunOptions(start_planned=True, skip_preflight=True), source
    ).execute()

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "--confirm-venue spot_mainnet" in outcome.message
    assert source.installed is False, "no host was built, no signal was taken"
    stored = JsonBotStore(data_root / "bots").load(BotId("aaaaaa"))
    assert stored.bot.state is BotLifecycleState.STOPPED, "nothing was started"


def test_resume_recovering_without_an_alert_channel_or_the_acknowledgement_is_refused_with_five(
    data_root: Path,
) -> None:
    source = _Source()

    outcome = RunCommand(
        _app(data_root), RunOptions(resume_recovering=True, skip_preflight=True), source
    ).execute()

    assert outcome is not None and outcome.code is ExitCode.CONFIGURATION
    assert "--i-accept-silent-failures" in outcome.message
    assert source.installed is False


def test_a_host_signal_the_machine_cannot_give_is_refused_with_two_before_the_preflight(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    source = _Source()

    outcome = RunCommand(
        _app(data_root), RunOptions(host_signal=HostSignalName.SDNOTIFY), source
    ).execute()

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "NOTIFY_SOCKET" in outcome.message
    assert source.installed is False


def test_a_stop_requested_while_the_app_boots_is_honoured_and_every_state_is_published(
    data_root: Path,
) -> None:
    """The entry point listens before `app.boot()`: a SIGTERM during the restore is a
    request to stop, honoured the moment the host serves - not a kill."""
    source = _Source()
    app = _app(data_root)
    command = RunCommand(
        app,
        RunOptions(
            resume_recovering=True, accept_silent_failures=True, skip_preflight=True
        ),
        source,
    )

    with _heard() as lines:
        original_install = source.install

        def install_then_fire(on_signal: Callable[[], None]) -> None:
            original_install(on_signal)
            source.fire()  # the operator stops the service as it begins to boot

        source.install = install_then_fire  # type: ignore[method-assign]
        outcome = command.execute()

    assert outcome is None
    assert source.restored == 1
    text = "\n".join(lines)
    for move in ("BOOTING -> SERVING", "SERVING -> DRAINING", "DRAINING -> STOPPED"):
        assert move in text, text
    states = [line.state for line in health_lines_in(text)]
    assert HostState.SERVING in states and HostState.DRAINING in states
    snapshot = FileHealthSnapshotSource(data_root / "state" / "health.json").read()
    assert snapshot is not None and snapshot.host_state is HostState.STOPPED
    assert snapshot.interval_s == 60, "the host's interval, not the default ten seconds"
    assert "no venue holds a RECOVERING bot" in text
