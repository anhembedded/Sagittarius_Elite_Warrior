"""`EPIC-038K` - `bot start` reaches a running host and runs the screen's own Start.

@details The owner runs several bots and wants Stop, edit the plan, then Start of one bot without
touching the others or restarting the host. This is that journey on the composed app over the fake
exchange, for Spot and for Futures: the operator's `IHostControl` writes a command file into the real
command directory, the host's own `HostedControlPoller` (built by the module's binding, over the
container's own dispatcher) reads it, and the screen's Start runs. Only the websocket and
the two waits are substituted - the sleep of the operator's writer is where the host gets its turn.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.kernel.app import App

from .futures_bots_world import GRID as FUTURES_GRID
from .futures_bots_world import booted_futures_bots
from .futures_fake_exchange import FUTURES
from .futures_fake_exchange import SYMBOL as FUTURES_SYMBOL
from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    FakeExchange,
    booted,
)

S = BotLifecycleState


class _HostHoldsTheLock(IInstanceProbe):
    def is_held(self) -> bool:
        return True


class _Operator:
    """A second shell on the host's data root, whose sleep is the host's turn."""

    def __init__(
        self, engine: App, directory: Path, deliver: Callable[[], None]
    ) -> None:
        self._engine = engine
        self._directory = directory
        self._deliver = deliver
        self._sent = 0

    def ask(self, request: HostControlRequest) -> HostControlReply:
        self._sent += 1
        container = self._engine.context.container
        host = container.resolve(HostedControlPoller)
        clock_s = [0.0]

        def the_host_gets_a_turn(seconds: float) -> None:
            clock_s[0] += seconds
            host.poll_once()
            self._deliver()

        return DirectoryHostControl(
            self._directory,
            _HostHoldsTheLock(),
            JsonlHostControlAudit(self._directory / AUDIT_FILE_NAME),
            container.resolve(IOperationsClock),
            lambda: f"{self._sent:032x}",
            the_host_gets_a_turn,
            lambda: clock_s[0],
        ).send(request, 15.0)


def _operator(engine: App, data_root: Path, deliver: Callable[[], None]) -> _Operator:
    directory = control_directory_of(data_root / "state")
    assert prepare_private_directory(directory) == ""
    return _Operator(engine, directory, deliver)


def _create(
    engine: App, venue: TradingVenue, symbol: str, config: dict[str, str]
) -> str:
    created = engine.dispatch(
        CreateBotCommand, CreateBotCommand("one", "grid", venue, symbol, config)
    )
    assert isinstance(created, BotCommandResult) and created.bot_id is not None
    return created.bot_id


def _state(store: IBotStore, bot_id: str) -> BotLifecycleState:
    return store.load(BotId(bot_id)).bot.state


def _ids(store: IBotStore) -> set[str]:
    return {stored.bot.bot_id.value for stored in store.load_all().bots}


def test_a_spot_bot_is_stopped_then_started_again_while_the_host_keeps_running(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner's case: Stop, then Start of ONE bot, with no restart of the host."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = _operator(app.engine, exchange.tmp_path, app.deliver)
        bot_id = _create(app.engine, SPOT, SYMBOL, GRID)

        first = operator.ask(HostControlRequest(HostControlAction.START, bot_id))
        assert first.status is HostControlStatus.DONE, first.message
        assert _state(app.store, bot_id) is S.RUNNING

        stopped = operator.ask(HostControlRequest(HostControlAction.STOP, bot_id))
        assert stopped.status is HostControlStatus.DONE, stopped.message
        assert _state(app.store, bot_id) is S.STOPPED

        again = operator.ask(HostControlRequest(HostControlAction.START, bot_id))
        assert again.status is HostControlStatus.DONE, again.message
        assert _state(app.store, bot_id) is S.RUNNING
        audit = (exchange.tmp_path / "state" / "control" / AUDIT_FILE_NAME).read_text(
            encoding="utf-8"
        )
        assert audit.count('"action": "start"') >= 2


def test_a_start_the_screen_would_refuse_is_refused_in_its_words_and_changes_nothing(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """J1a: one active bot per symbol. The second bot's `bot start` is the screen's refusal."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = _operator(app.engine, exchange.tmp_path, app.deliver)
        running = _create(app.engine, SPOT, SYMBOL, GRID)
        assert (
            operator.ask(HostControlRequest(HostControlAction.START, running)).status
            is HostControlStatus.DONE
        )
        second = _create(app.engine, SPOT, SYMBOL, GRID)

        reply = operator.ask(HostControlRequest(HostControlAction.START, second))

        assert reply.status is HostControlStatus.REFUSED
        assert running in reply.message
        assert _state(app.store, second) is S.DRAFT
        assert _state(app.store, running) is S.RUNNING


def test_a_halted_bot_is_not_started_from_a_file_and_stays_halted(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        operator = _operator(app.engine, exchange.tmp_path, app.deliver)
        halted = _create(app.engine, SPOT, SYMBOL, GRID)
        started = app.engine.dispatch(StartBotCommand, StartBotCommand(halted))
        assert isinstance(started, BotCommandResult) and started.accepted
        app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=SPOT))
        app.deliver()
        assert _state(app.store, halted) is S.HALTED

        reply = operator.ask(HostControlRequest(HostControlAction.START, halted))

        assert reply.status is HostControlStatus.REFUSED
        assert "--resume-halted" in reply.message
        assert _state(app.store, halted) is S.HALTED


def test_a_futures_bot_is_started_stopped_and_started_again_from_the_command_directory(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(futures.tmp_path))
    with booted_futures_bots(futures) as app:
        operator = _operator(app.engine, futures.tmp_path, app.deliver)
        bot_id = _create(app.engine, FUTURES, FUTURES_SYMBOL, FUTURES_GRID)

        started = operator.ask(HostControlRequest(HostControlAction.START, bot_id))
        assert started.status is HostControlStatus.DONE, started.message
        assert _state(app.store, bot_id) is S.RUNNING
        assert app.resting(), "the Futures ladder rests on the exchange"

        stopped = operator.ask(
            HostControlRequest(HostControlAction.STOP, bot_id, close_position=True)
        )
        assert stopped.status is HostControlStatus.DONE, stopped.message
        assert _state(app.store, bot_id) is S.STOPPED

        again = operator.ask(HostControlRequest(HostControlAction.START, bot_id))
        assert again.status is HostControlStatus.DONE, again.message
        assert _state(app.store, bot_id) is S.RUNNING


def test_a_futures_mainnet_start_is_not_run_until_the_venue_is_typed(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision O8 across the file: no `--confirm-venue`, nothing is opened or started."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(futures.tmp_path))
    with booted_futures_bots(futures) as app:
        operator = _operator(app.engine, futures.tmp_path, app.deliver)
        bot_id = _create(
            app.engine, TradingVenue.FUTURES_MAINNET, FUTURES_SYMBOL, FUTURES_GRID
        )

        reply = operator.ask(HostControlRequest(HostControlAction.START, bot_id))

        assert reply.status is HostControlStatus.REFUSED
        assert "--confirm-venue futures_mainnet" in reply.message
        assert _state(app.store, bot_id) is S.DRAFT
        assert app.resting() == {}
