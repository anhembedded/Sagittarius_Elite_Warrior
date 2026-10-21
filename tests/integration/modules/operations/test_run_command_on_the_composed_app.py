"""`RunCommand` on the graph `createapp_on()` builds (`EPIC-038D`).

The unit tests construct the host from doubles, and so prove nothing about wiring
(`CS-002`): this builds the real application - the bots module with its store, the
operations module with its snapshot and cadence, the trading module with its probe -
and runs the command against it. Only the signal is by hand (the source is the port's
double); the process-level proof with real signals is `test_run_process.py`.

Nothing here reaches an exchange: no key, no bot to start.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.operations.run_command_support import (
    Plan,
    Source,
    app_on,
    heard,
)


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


def test_an_unconfirmed_mainnet_start_planned_boots_the_host_skips_the_bot_and_says_how_to_start_it(
    data_root: Path,
) -> None:
    """`EPIC-045F`: this was exit 2 before boot, which systemd does not restart, so every other bot
    was left unattended. The host now serves, warns about the bot it left and starts nothing for it."""
    _seed_mainnet_bot(data_root, "aaaaaa")
    app = app_on(data_root)
    app.container.singleton(IBotPlan, Plan("aaaaaa"))  # type: ignore[type-abstract]
    source = Source()
    original_install = source.install

    def install_then_fire(on_signal: Callable[[], None]) -> None:
        original_install(on_signal)
        source.fire()

    source.install = install_then_fire  # type: ignore[method-assign]

    outcome = RunCommand(
        app, RunOptions(start_planned=True, skip_preflight=True), source
    ).execute()

    assert outcome is None, "the host ran and stopped on the signal"
    assert source.installed is True
    step = next(
        s
        for s in RunCommand(
            app, RunOptions(start_planned=True, skip_preflight=True), Source()
        )._steps()
        if s.name == "start-planned"
    )
    with heard() as step_lines:
        step.run()
    text = "\n".join(step_lines)
    assert "bot aaaaaa on spot_mainnet was not started" in text, text
    assert "bot start aaaaaa --confirm-venue spot_mainnet" in text
    stored = JsonBotStore(data_root / "bots").load(BotId("aaaaaa"))
    assert stored.bot.state is BotLifecycleState.STOPPED, "nothing was started"


def test_resume_recovering_without_an_alert_channel_or_the_acknowledgement_is_refused_with_five(
    data_root: Path,
) -> None:
    source = Source()

    outcome = RunCommand(
        app_on(data_root),
        RunOptions(resume_recovering=True, skip_preflight=True),
        source,
    ).execute()

    assert outcome is not None and outcome.code is ExitCode.CONFIGURATION
    assert "--i-accept-silent-failures" in outcome.message
    assert source.installed is False


def test_resume_halted_without_an_alert_channel_or_the_acknowledgement_is_refused_with_five(
    data_root: Path,
) -> None:
    """`EPIC-042E`: nobody watching is refused for this flag as for `--resume-recovering`, and the
    sentence names the flag the operator typed."""
    source = Source()

    outcome = RunCommand(
        app_on(data_root),
        RunOptions(resume_halted=True, skip_preflight=True),
        source,
    ).execute()

    assert outcome is not None and outcome.code is ExitCode.CONFIGURATION
    assert "--resume-halted" in outcome.message
    assert "--resume-recovering" not in outcome.message
    assert "--i-accept-silent-failures" in outcome.message
    assert source.installed is False


def test_resume_halted_runs_before_resume_recovering_so_only_earlier_halts_are_replanned(
    data_root: Path,
) -> None:
    command = RunCommand(
        app_on(data_root),
        RunOptions(
            resume_halted=True,
            resume_recovering=True,
            accept_silent_failures=True,
            skip_preflight=True,
        ),
        Source(),
    )

    names = [step.name for step in command._steps()]

    assert names.index("resume-halted") < names.index("resume-recovering")


def test_a_host_signal_the_machine_cannot_give_is_refused_with_two_before_the_preflight(
    data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    source = Source()

    outcome = RunCommand(
        app_on(data_root), RunOptions(host_signal=HostSignalName.SDNOTIFY), source
    ).execute()

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "NOTIFY_SOCKET" in outcome.message
    assert source.installed is False


def _seed_mainnet_bot_in(
    data_root: Path, bot_id: str, state: BotLifecycleState
) -> None:
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
                BotLifecycle(state),
                datetime(2026, 10, 1, tzinfo=UTC),
            )
        )
    )


@pytest.mark.parametrize(
    "state",
    [BotLifecycleState.RUNNING, BotLifecycleState.PAUSED, BotLifecycleState.RECOVERING],
    ids=lambda s: s.value,
)
def test_an_unconfirmed_mainnet_resume_recovering_is_refused_with_two_and_nothing_boots(
    data_root: Path, state: BotLifecycleState
) -> None:
    """Decision O8: not a quiet skip. The refusal runs before the app boots, and it is the
    boot that turns a bot left RUNNING or PAUSED on disk into RECOVERING - a crash leaves
    exactly that - so all three states are judged. The bot stays as the file has it, the
    host does not serve, and the message names the flag that would have allowed it."""
    _seed_mainnet_bot_in(data_root, "aaaaaa", state)
    source = Source()

    outcome = RunCommand(
        app_on(data_root),
        RunOptions(
            resume_recovering=True, accept_silent_failures=True, skip_preflight=True
        ),
        source,
    ).execute()

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "--confirm-venue spot_mainnet" in outcome.message
    assert "aaaaaa" in outcome.message
    assert source.installed is False, "no host was built, no signal was taken"
    stored = JsonBotStore(data_root / "bots").load(BotId("aaaaaa"))
    assert stored.bot.state is state, "nothing booted, so nothing was restored"


def test_a_stop_requested_before_serving_starts_and_resumes_nothing_on_the_composed_app(
    data_root: Path,
) -> None:
    """A planned bot at rest and a stop that arrives as the app boots: the bot stays at
    rest. (`--start-planned` on a testnet bot would otherwise open that venue's session.)"""
    JsonBotStore(data_root / "bots").save(
        StoredBot(
            Bot(
                BotId("aaaaaa"),
                BotDefinition(
                    "paper",
                    "grid",
                    TradingVenue.SPOT_TESTNET,
                    "BTCUSDT",
                    {"lower": "1"},
                ),
                BotLifecycle(BotLifecycleState.STOPPED),
                datetime(2026, 10, 1, tzinfo=UTC),
            )
        )
    )
    source = Source()
    app = app_on(data_root)
    app.container.singleton(IBotPlan, Plan("aaaaaa"))  # type: ignore[type-abstract]
    command = RunCommand(
        app, RunOptions(start_planned=True, skip_preflight=True), source
    )
    original_install = source.install

    def install_then_fire(on_signal: Callable[[], None]) -> None:
        original_install(on_signal)
        source.fire()

    source.install = install_then_fire  # type: ignore[method-assign]
    with heard() as lines:
        outcome = command.execute()

    assert outcome is None
    text = "\n".join(lines)
    assert "step start-planned skipped" in text, text
    assert "[start-planned]" not in text
    stored = JsonBotStore(data_root / "bots").load(BotId("aaaaaa"))
    assert stored.bot.state is BotLifecycleState.STOPPED


def test_a_stop_requested_while_the_app_boots_is_honoured_and_every_state_is_published(
    data_root: Path,
) -> None:
    """The entry point listens before `app.boot()`: a SIGTERM during the restore is a
    request to stop, honoured the moment the host serves - not a kill."""
    source = Source()
    app = app_on(data_root)
    command = RunCommand(
        app,
        RunOptions(
            resume_recovering=True, accept_silent_failures=True, skip_preflight=True
        ),
        source,
    )

    with heard() as lines:
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
    assert "step resume-recovering skipped" in text, text
    assert "no venue holds a RECOVERING bot" not in text, "the resume step ran"
