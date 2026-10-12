"""The composed app keeps `state/health.json` while it lives (`EPIC-038C`, D5).

A test that builds the publisher proves the publisher, not that the app starts
it (`CS-002`): this boots the graph `create_app()` builds, with no exchange, and
reads the file a second process would read. It also reads the bots through the
two dispatches - the Bots tab's `ListBotsQuery` and the status report - on that
same graph, so the parity is asserted where the handlers are bound, not where a
test constructed them.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)
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
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


def _bot(bot_id: str, venue: TradingVenue, state: BotLifecycleState) -> StoredBot:
    definition = BotDefinition(
        name=f"bot {bot_id}",
        kind="grid",
        venue=venue,
        symbol="BTCUSDT",
        config={"lower": "1"},
    )
    created = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    return StoredBot(Bot(BotId(bot_id), definition, BotLifecycle(state), created))


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    bots = tmp_path / "state" / "bots"
    store = JsonBotStore(bots)
    store.save(_bot("aaaaaa", TradingVenue.SPOT_TESTNET, BotLifecycleState.DRAFT))
    store.save(_bot("bbbbbb", TradingVenue.FUTURES_TESTNET, BotLifecycleState.STOPPED))
    (bots / "cccccc.json").write_text("not json", encoding="utf-8")
    return tmp_path


@pytest.fixture
def booted(data_root: Path) -> Iterator[App]:
    app = create_app(ConfigManager())
    app.boot()
    try:
        yield app
    finally:
        app.stop()


def test_a_booted_writable_app_publishes_its_snapshot_and_a_stop_marks_it(
    data_root: Path,
) -> None:
    path = data_root / "state" / "health.json"
    app = create_app(ConfigManager())
    app.boot()
    try:
        running = FileHealthSnapshotSource(path).read()
    finally:
        app.stop()
    stopped = FileHealthSnapshotSource(path).read()

    assert running is not None
    assert running.host_state is HostState.SERVING
    assert running.interval_s > 0
    assert stopped is not None
    assert stopped.host_state is HostState.STOPPED
    assert stopped.written_at >= running.written_at


def test_a_read_only_copy_leaves_the_hosts_snapshot_alone(data_root: Path) -> None:
    lock = data_root / "state" / "instance.lock"
    first = InstanceAccess.acquire(lock)
    second = InstanceAccess.acquire(lock)
    assert first.read_only is False
    assert second.read_only is True

    app = create_app(ConfigManager(), second)
    app.boot()
    app.stop()
    first.release()

    assert not (data_root / "state" / "health.json").exists()


def test_the_status_report_and_the_bots_tab_list_agree_on_the_composed_graph(
    booted: App,
) -> None:
    dispatcher = booted.container.resolve(ICommandDispatcher)
    screen = dispatcher.dispatch(ListBotsQuery, ListBotsQuery())
    report = dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery())
    assert isinstance(screen, BotList)
    assert isinstance(report, BotStatusReport)

    assert [
        (b.bot_id, b.name, b.kind, b.venue.value, b.symbol, b.state.value)
        for b in screen.bots
    ] == [(b.bot_id, b.name, b.kind, b.venue, b.symbol, b.state) for b in report.bots]
    assert [r.name for r in screen.refused] == ["cccccc.json"]
    assert [Path(u.path).name for u in report.unreadable] == ["cccccc.json"]
    assert Path(report.unreadable[0].path).is_file()
