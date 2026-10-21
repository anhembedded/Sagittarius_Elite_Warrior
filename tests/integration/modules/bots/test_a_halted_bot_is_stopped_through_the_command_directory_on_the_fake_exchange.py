"""`EPIC-038J` - the owner's case: a HALTED Spot bot whose base asset is gone is stopped on a running host.

@details On 2026-10-17 a Spot bot sat HALTED with the owner's coin sold by hand; its resume was
refused, the headless host had no Stop, and a HALTED bot counts as active (ADR D20), so no new bot
could start on the symbol. This journey is that case on the composed app over the fake exchange:
the halted bot blocks a second bot; the operator's `IHostControl` writes a command file into the
real command directory; the host's own `HostedControlPoller` (built by the module's binding, over
the container's own dispatcher) reads it, and the screen's Stop runs; the bot is STOPPED and the
second bot starts. Only the websocket and the two waits are substituted - the sleep of the
operator's writer is where the host gets its turn, so nothing here sleeps for real.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    AUDIT_FILE_NAME,
    control_directory_of,
    prepare_private_directory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_control import (
    DirectoryHostControl,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.hosted_control_poller import (
    HostedControlPoller,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.jsonl_host_control_audit import (
    JsonlHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
)

from .grid_fake_exchange import (
    BASELINE,
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
)

S = BotLifecycleState


class _HostHoldsTheLock(IInstanceProbe):
    def is_held(self) -> bool:
        return True


def _create(app: BootedApp, name: str) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand(name, "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult) and created.bot_id is not None
    return created.bot_id


def _start(app: BootedApp, bot_id: str) -> BotCommandResult:
    answer = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
    assert isinstance(answer, BotCommandResult)
    return answer


def _operator(
    app: BootedApp, directory: Path, command_id: str, *, also_deliver: bool = True
) -> DirectoryHostControl:
    """The operator's writer; its sleep is the host's turn (and the exchange's reports)."""
    container = app.engine.context.container
    host = container.resolve(HostedControlPoller)
    clock_s = [0.0]

    def the_host_gets_a_turn(seconds: float) -> None:
        clock_s[0] += seconds
        host.poll_once()
        if also_deliver:
            app.deliver()

    return DirectoryHostControl(
        directory,
        _HostHoldsTheLock(),
        JsonlHostControlAudit(directory / AUDIT_FILE_NAME),
        container.resolve(IOperationsClock),
        lambda: command_id,
        the_host_gets_a_turn,
        lambda: clock_s[0],
    )


def _halted_without_its_coin(app: BootedApp) -> str:
    """The incident: HALTED, the order session open (the refused resume opened it), the coin sold."""
    halted = _create(app, "old run")
    assert _start(app, halted).accepted
    app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=SPOT))
    app.deliver()
    assert app.bot(halted).state is S.HALTED
    app.scope.session_state.enable(set(), spot_baseline_holdings=dict(BASELINE))
    app.urls.spot_account.withdraw_free(
        "BTC", app.urls.spot_account.free_balance("BTC")
    )
    assert app.urls.spot_account.free_balance("BTC") == Decimal(0)
    return halted


def test_a_halted_bot_without_its_coin_is_stopped_from_the_command_directory_and_a_new_run_starts(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        halted = _halted_without_its_coin(app)
        fresh = _create(app, "new run")
        blocked = _start(app, fresh)
        assert blocked.refusal is BotRefusal.ONE_ACTIVE_BOT_PER_SYMBOL

        directory = control_directory_of(exchange.tmp_path / "state")
        assert prepare_private_directory(directory) == ""
        operator = _operator(app, directory, "d" * 32)

        reply = operator.send(HostControlRequest(HostControlAction.STOP, halted), 15.0)

        assert reply.status is HostControlStatus.DONE, reply.message
        assert app.bot(halted).state is S.STOPPED
        assert sorted(p.name for p in directory.iterdir()) == [AUDIT_FILE_NAME]
        assert _start(app, fresh).accepted
        assert app.bot(fresh).state in (S.STARTING, S.RUNNING)
        audit = (directory / AUDIT_FILE_NAME).read_text(encoding="utf-8")
        assert '"verdict": "received"' in audit and '"verdict": "executed"' in audit


def test_a_stop_for_a_bot_that_is_already_at_rest_is_refused_in_the_screens_words(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        resting_bot = _create(app, "never started")
        directory = control_directory_of(exchange.tmp_path / "state")
        assert prepare_private_directory(directory) == ""

        reply = _operator(app, directory, "e" * 32).send(
            HostControlRequest(HostControlAction.STOP, resting_bot), 15.0
        )

        assert reply.status is HostControlStatus.REFUSED
        assert app.bot(resting_bot).state is S.DRAFT


def test_a_running_bot_is_paused_and_resumed_from_the_command_directory(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`bot pause` and `bot resume` reach the screen's Pause and Resume through the composed app's
    own bindings (`PauseBotForHostCommand`, `ResumeBotForHostCommand`), and the ladder keeps resting."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        running = _create(app, "grid")
        assert _start(app, running).accepted
        assert app.bot(running).state is S.RUNNING
        directory = control_directory_of(exchange.tmp_path / "state")
        assert prepare_private_directory(directory) == ""

        paused = _operator(app, directory, "1" * 32).send(
            HostControlRequest(HostControlAction.PAUSE, running), 15.0
        )
        state_after_pause = app.bot(running).state
        resumed = _operator(app, directory, "2" * 32).send(
            HostControlRequest(HostControlAction.RESUME, running), 15.0
        )

        assert paused.status is HostControlStatus.DONE, paused.message
        assert state_after_pause is S.PAUSED
        assert resumed.status is HostControlStatus.DONE, resumed.message
        assert app.bot(running).state is S.RUNNING


def test_a_halted_bot_whose_coin_is_gone_is_refused_by_the_screens_readiness_and_stays_halted(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        halted = _halted_without_its_coin(app)
        directory = control_directory_of(exchange.tmp_path / "state")
        assert prepare_private_directory(directory) == ""

        reply = _operator(app, directory, "3" * 32).send(
            HostControlRequest(HostControlAction.RESUME, halted), 15.0
        )

        assert reply.status is HostControlStatus.REFUSED
        assert "Resume is blocked" in reply.message and "0 BTC free" in reply.message
        assert app.bot(halted).state is S.HALTED


def test_a_stop_while_the_order_session_is_closed_opens_it_and_the_bot_stops(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner's answer "B" (2026-10-17): the screen's Stop does not open the venue's order
    session, so after an Emergency Stop the bot would wait in STOPPING for a session nobody opens.
    `bot stop` opens it itself, as Start and Resume do, and the bot reaches STOPPED."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        halted = _create(app, "old run")
        assert _start(app, halted).accepted
        app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=SPOT))
        app.deliver()
        assert app.scope.session_state.enabled is False
        directory = control_directory_of(exchange.tmp_path / "state")
        assert prepare_private_directory(directory) == ""

        reply = _operator(app, directory, "f" * 32).send(
            HostControlRequest(HostControlAction.STOP, halted), 15.0
        )

        assert reply.status is HostControlStatus.DONE, reply.message
        assert app.scope.session_state.enabled is True, "the stop opened the session"
        assert app.bot(halted).state is S.STOPPED


def test_the_module_binds_the_operators_port_and_the_hosts_poller_in_the_composed_app(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        container = app.engine.context.container

        assert isinstance(container.resolve(IHostControl), DirectoryHostControl)
        assert isinstance(container.resolve(HostedControlPoller), HostedControlPoller)
