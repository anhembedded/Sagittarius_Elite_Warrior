import os
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """`BUG-121` — this tier's hang sits the main thread inside Qt's C++ event
    loop or `Executor.shutdown(wait=True)`, neither of which ever returns to
    the interpreter to run pytest-timeout's `signal`-method handler
    (`pyproject.toml`'s own `timeout` comment). `method="thread"` runs the
    watchdog on its own OS thread, so it fires regardless of what the main
    thread is blocked in — scoped to this tier alone (an independent review
    on `BUG-131`'s PR #246 found an earlier version of this fix set it
    globally, taking every OTHER tier's per-test signal-isolation traceback
    away for a hang that only reproduces here)."""
    marker = pytest.mark.timeout(60, method="thread")
    for item in items:
        item.add_marker(marker)


from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    FakeRangeCoverage,
    fully_covered,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.tests.conftest import real_main_window
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    MOCK_KLINE_COUNT,
    SEEDED_SYMBOLS,
    build_mock_klines,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


class _FakeResponse:
    """A dispatch result that is safe to build on a worker thread (`BUG-056`).

    @details This used to be a `MagicMock()`, constructed fresh inside
    `mock_dispatch` — which runs on whichever thread called `dispatch`, and in
    this suite that is regularly a `ThreadManager` worker (`_run_load_history`,
    `_sync_market_data`, the Database scans).

    `unittest.mock` is not thread-safe. Building a `MagicMock` runs
    `_mock_set_magics`, which mutates the mock's *type*, and doing that while
    the main thread is garbage-collecting aborted the interpreter partway
    through a combined `integration/ + sanity/` run — no test `FAILED`, just
    `Fatal Python error: Aborted`. Same root cause as the deadlock documented
    in `test_main_window_state.py`, a different symptom.

    Plain attributes have nothing to mutate and nothing to race, so this is
    the whole fix. Deliberately strict rather than permissive: a consumer
    reading a field this does not define now raises `AttributeError` naming
    it, instead of silently receiving a truthy `Mock` — which is how a mock
    can make a test pass for the wrong reason.
    """

    __slots__ = ("data", "success")

    def __init__(self, data=None, success: bool = True) -> None:
        self.success = success
        self.data = [] if data is None else data


@pytest.fixture
def seeded_history():
    """The history store every UI integration test reads through.

    `EPIC-025` PR 1.1 — exposed as its own fixture because a test that needs
    *more* history than the default page (the load-more ones) now seeds it
    instead of hand-rolling a dispatcher that answers differently depending on
    whether `end_time` was set. That hand-rolled version's own docstring
    called itself "real handler behavior, just without a real database"; with
    a store there is nothing left to simulate.
    """
    history = FakeHistoricalKlines()
    for symbol in SEEDED_SYMBOLS:
        # Chronological: `build_mock_klines` hands back newest-first because
        # that is what a dispatch returned and the screen reversed. A store
        # has no order of its own — the port applies `newest_first` on read.
        history.seed(list(reversed(build_mock_klines(symbol))))
    return history


@pytest.fixture
def market_stream():
    """The live stream every UI integration test opens and releases.

    `EPIC-025` PR 1.1b — its own fixture for the same reason `seeded_history`
    is: a test that asserts "this screen is streaming ETHUSDT at 1m" reads it
    directly, where before it had to find the right dispatch call and trust a
    `MagicMock`'s `.success`.
    """
    return FakeMarketStream()


#: The window the scripted coverage answer reports as complete. Any two
#: instants in the right order would do — a screen renders them, it does not
#: compute with them, and `mock_klines.build_mock_klines` decides what is
#: actually stored.
_COVERED_FROM = datetime(2024, 1, 1, tzinfo=UTC)
_COVERED_TO = datetime(2024, 1, 2, tzinfo=UTC)


@pytest.fixture
def range_coverage():
    """The coverage probe every Backtest integration test reads.

    `EPIC-025` PR 1.2 — scripted to "fully covered" for the shard the seeded
    history fills, because that is the state these tests were written
    against: the mocked dispatcher used to answer exactly this.
    """
    fake = FakeRangeCoverage()
    covered = fully_covered(_COVERED_FROM, _COVERED_TO, candles=MOCK_KLINE_COUNT)
    for symbol in SEEDED_SYMBOLS:
        for interval in (TimeFrame.ONE_MINUTE, TimeFrame.ONE_SECOND):
            fake.answer_with(covered, symbol=symbol, interval=interval)
    return fake


@pytest.fixture
def symbol_catalog():
    """The tradeable-symbol list every picker in these tests opens."""
    return FakeSymbolCatalog(SEEDED_SYMBOLS)


@pytest.fixture
def app_engine(
    request,
    monkeypatch,
    tmp_path,
    seeded_history,
    market_stream,
    range_coverage,
    symbol_catalog,
):
    """
    Boot the Sagittarius Engine with all configurations but mock the
    dispatcher backend. Defaults to dev.mode=False; parametrize indirectly
    with `True` to boot with dev mode on.

    Deliberately keeps the REAL `IThreadManager` (a genuine
    `ThreadPoolExecutor`, see `sagittarius_engine/infrastructure/thread_manager.py`)
    unmocked — several tests in this directory exist specifically to
    reproduce race conditions that only manifest with real background
    threads, not a synchronous `submit()` stub.
    """
    dev_mode = getattr(request, "param", False)

    # BUG-056 — flush the PREVIOUS test's pending widget deletions before this
    # one starts any background work.
    #
    # `qtbot.addWidget()` schedules `deleteLater()` as part of qtbot's own
    # teardown, which runs *after* every other fixture here (fixtures tear down
    # in reverse dependency order, and qtbot is the innermost). Nothing pumps
    # the event loop after that, so those deletions sit queued until pytest-qt
    # pumps at the NEXT test's setup — by which point this fixture has booted
    # an engine and a mode's first load has a worker running. Any
    # allocation that worker makes can then trigger a GC that runs shiboken
    # destructors for those just-freed widgets **on the worker thread**, and
    # the interpreter aborts: `Fatal Python error: Aborted` partway through a
    # run with no test `FAILED`.
    #
    # Draining here is the one moment when that is safe — the previous
    # engine's pool is already shut down (see this fixture's teardown) and this
    # one has not started. `main_window`'s own teardown drains what it owns;
    # this catches what qtbot deletes afterwards, for every test in the
    # directory.
    app = QApplication.instance()
    if app is not None:
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

    config_manager = ConfigManager()

    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    app_json = os.path.join(base_dir, "src", "config", "app_config.json")
    real_user_json = os.path.join(base_dir, "src", "config", "user_config.json")

    # Loaded writable from a tmp copy, not the real file: Tools → Options'
    # Apply calls ConfigManager.save(), and any test in this directory that
    # exercises it (directly or incidentally) must not overwrite the actual
    # repo config on every
    # run — both a bad side effect and non-hermetic across parallel runs.
    user_json = tmp_path / "user_config.json"
    if os.path.exists(real_user_json):
        with open(real_user_json) as src:
            user_json.write_text(src.read())
    else:
        user_json.write_text("{}")

    config_manager.load_json(app_json)
    config_manager.load_json(str(user_json), writable=True)
    if dev_mode:
        config_manager.load_dict({"dev.mode": True})

    engine = create_app(config_manager)

    def mock_dispatch(command_type, command_obj):
        # `ArmStrategyCommandHandler`/`DisarmStrategyCommandHandler` are run
        # for real rather than faked: `StrategyArmingCoordinator.armed_summary()`
        # reads its state from `LiveStrategySession.config`, which only the
        # real handler mutates — a fabricated `ArmStrategyResult(armed=True)`
        # would report success while leaving the session (and therefore the
        # card's own "what is armed" label) unchanged. Both handlers are
        # cheap, synchronous, and take only container-resolved collaborators,
        # so the container builds them, as the real dispatcher does.
        if command_type in (ArmStrategyCommandHandler, DisarmStrategyCommandHandler):
            return engine.context.container.resolve(command_type).execute(command_obj)
        if command_type is ExecuteOrderCommand:
            # `EPIC-024B` — the manual order card's real-Qt-click test needs
            # the REAL `ExecuteOrderCommandHandler`, same reasoning as the
            # two branches above: a fabricated `ExecuteOrderResult` would
            # report success/failure without ever exercising the safety
            # gates the click is supposed to prove reachable. Every
            # collaborator below is unconditionally container-registered
            # (see `binance_bot_module.py` / `EPIC-024A`), so this never
            # touches the network — this test suite's app config always
            # boots with `TradingVenue.DISABLED` (`src/config/app_config.json`),
            # which `_first_blocked_safety_gate()` trips before any of the
            # network-touching collaborators (`account_reader`,
            # `preview_handler`, the exchange session) are ever called.
            # `EPIC-028B`: the command names that venue itself, and the
            # handler refuses it before resolving anything.
            handler = ExecuteOrderCommandHandler(
                engine.context.container.resolve(VenueTradingScopes),
                engine.context.container.resolve(PreviewOrderQueryHandler),
                engine.context.container.resolve(TradingLimitPolicy),
            )
            return handler.execute(command_obj)
        if command_type is GetOpenPositionsQuery:
            # `GetOpenPositionsQueryHandler` itself builds a real
            # `FuturesTradingClient` and hits the network
            # (`get_positions()`) unconditionally — safe to do against a
            # real exchange/fake server (see
            # `test_manual_order_pipeline_against_fake_server.py`), but not
            # something this offscreen Qt suite's shared engine should do on
            # every manual-order click. The order path only wants a real
            # tuple shape back (it iterates `positions` directly), not a
            # network round trip, so a flat empty tuple —
            # "no open position for any symbol" — is the correct fixture
            # answer here, same spirit as the `_FakeResponse` branches below.
            return ()

        response = _FakeResponse()
        # `EPIC-025` PR 1.1 removed this stub's largest branch. The klines read
        # is `IHistoricalKlines` now, answered by the seeded fake registered
        # below, so there is no `str | list[str]` shape to mirror and no
        # `{symbol: klines}` fan-out to hand-roll here. What the old branch's
        # long comment warned about — a stub that handled only the single-`str`
        # shape would short-circuit `isinstance(results, dict)` and skip
        # `feed_all()` — cannot happen against a typed port: `load()` and
        # `load_many()` have one return type each.
        # `EPIC-025` PR 1.2 removed the last branch that mattered: the
        # coverage probe is `IRangeCoverage` now, answered by the fake
        # registered below. `BUG-072`'s shape mismatch — a `_FakeResponse`
        # reaching `run_preview()` where production expects a
        # `BacktestRangeCoverage`, then crossing `_previewDataReadySignal`'s
        # loosely-typed `object` argument and risking a native crash — cannot
        # be built out of a typed port.
        response.data = []
        return response

    monkeypatch.setattr(engine, "dispatch", mock_dispatch)

    # `EPIC-025` PR 1.1a/1.1b — the history read and the live stream are
    # ports, so they are substituted at configuration (the container) rather
    # than by intercepting a dispatch. `testing-rule.md` calls that the
    # boundary a test should draw.
    engine.context.container.singleton(IHistoricalKlines, lambda _c: seeded_history)
    engine.context.container.singleton(IMarketStream, lambda _c: market_stream)
    engine.context.container.singleton(IRangeCoverage, lambda _c: range_coverage)
    engine.context.container.singleton(ISymbolCatalog, lambda _c: symbol_catalog)

    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher

    container_dispatcher = engine.context.container.resolve(IDispatcher)
    monkeypatch.setattr(container_dispatcher, "dispatch", mock_dispatch)

    engine.boot()
    yield engine

    # BUG-056 — no background task may outlive the test that started it.
    #
    # pytest-qt pumps the Qt event loop during the NEXT test's setup, which is
    # where the previous test's `deleteLater()` calls finally destroy their
    # widgets. If a `ThreadManager` worker from the finished test is still
    # running then, any allocation it makes can trigger a GC that runs
    # shiboken destructors for those just-freed Qt objects **on the worker
    # thread** — and the interpreter aborts. Observed as
    # `Fatal Python error: Aborted` / `Segmentation fault` partway through a
    # run with no test `FAILED`, the main thread sitting in
    # `pytest_runtest_setup -> _process_events`.
    #
    # `engine.stop()` alone does not prevent it: `ThreadManagerExtension`
    # deliberately calls `shutdown(wait=False)` so production shutdown never
    # blocks (see `BUG-041`), which returns while workers are still running.
    # The `main_window` fixture drains for the tests that use it; this covers
    # every test in this directory, including any that builds its own window.
    #
    # Safe to call twice — `ThreadPoolExecutor.shutdown` is idempotent, which
    # is why the `main_window` fixture doing the same is not a conflict.
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    thread_manager = engine.context.container.resolve(IThreadManager)
    if thread_manager is not None:
        thread_manager.shutdown(wait=True)
        # `BUG-121` — `shutdown(wait=True)` is supposed to block until every
        # submitted task has actually returned; a worker still alive right
        # after it returns is exactly the leak that crashed the interpreter
        # on a LATER test (the GC-on-worker-thread abort this fixture's own
        # comment above describes), so name it here instead of letting it
        # surface three tests later with no test at fault.
        stats = thread_manager.stats()
        assert stats.in_flight == 0, (
            "a ThreadManager worker survived app_engine's shutdown(wait=True) "
            f"(BUG-121): {stats.in_flight} still in flight "
            f"(submitted={stats.submitted}, completed={stats.completed})"
        )

    engine.stop()


@pytest.fixture
def main_window(qapp, qtbot, app_engine):
    """
    @brief Instantiate the MainWindow with the mocked engine.
    @details Teardown blocks until this engine's IThreadManager pool has
    actually drained, before this fixture's own generator resumes — which,
    since fixtures tear down in reverse dependency order, happens *before*
    app_engine's teardown calls engine.stop(). Without this, a background
    load left running past the end of a test can still be mid-emit when this
    test's Qt widgets get garbage-collected, touching an already-deleted
    pyqtgraph object — a real, reproduced crash (Windows access violation),
    not a hypothetical one. A bare sleep-based grace period was tried first
    and was NOT reliable; thread_manager.shutdown(wait=True) blocks until
    every submitted task has returned. Production shutdown still uses
    wait=False (see thread_manager_module.py): only this test fixture needs
    to await widget-teardown safety.
    """
    window = real_main_window(app_engine)
    window.show()
    yield window

    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    thread_manager = app_engine.context.container.resolve(IThreadManager)
    if thread_manager is not None:
        thread_manager.shutdown(wait=True)
        # `BUG-121` — same reasoning as `app_engine`'s own drain above: prove
        # the mechanism this docstring promises ("blocks until ... pool has
        # actually drained") actually held for this test's worker, instead of
        # trusting that it did.
        stats = thread_manager.stats()
        assert stats.in_flight == 0, (
            "a ThreadManager worker survived main_window's shutdown(wait=True) "
            f"(BUG-121): {stats.in_flight} still in flight "
            f"(submitted={stats.submitted}, completed={stats.completed})"
        )

    # ChartCard's helpers that watch its canvas (the cached-frame controller
    # and the FPS meter) install event filters on it — an event filter is a
    # raw pointer on the filtered widget's side, not a Qt-managed ownership
    # link. ChartCard.cleanup() disposes them, but a screen that keeps its
    # cards for its whole life (Backtest's `chart_cards`) never calls it for
    # the cards still current when a test ends, leaving Qt's deleteLater()
    # teardown to destroy `canvas` out from under a still-alive helper, or
    # vice versa — a real, reproduced Windows access violation.
    for host in window.hosts.values():
        cards = getattr(host.view, "chart_cards", None)
        if cards:
            for card in cards:
                if hasattr(card, "cleanup"):
                    card.cleanup()
            cards.clear()

    # qtbot.addWidget(main_window), called inside every test body, only
    # schedules window.deleteLater() as part of *qtbot's own* teardown —
    # which, since fixtures tear down in reverse dependency order, runs
    # AFTER this fixture's teardown code has already returned. Nothing
    # pumps the event loop in between, so that DeferredDelete doesn't
    # actually get processed until whatever next pumps the (session-wide,
    # shared-across-tests) Qt event loop — which turned out to be the
    # *next* test's own qtbot.waitSignal/waitUntil call, interleaving this
    # window's teardown with the next test's fresh widgets. Explicitly
    # closing and deleting here, then draining, ensures this window is
    # fully gone before the next test's setup begins instead of leaking
    # its destruction into that test. (qtbot's later redundant
    # deleteLater() call on an already-deleted widget is a safe no-op.)
    window.close()
    window.deleteLater()
    qtbot.wait(100)


@pytest.fixture
def navigate(qapp, qtbot, main_window):
    """
    Shows a mode the way a user does, by triggering its mode-bar action
    (`EPIC-033C`), and returns the mode's view and presenter under the keys
    the sidebar-era router used, so every screen test reads them one way.
    """

    def _navigate(route: str) -> dict:
        action = main_window.findChild(QAction, f"action::workbench.mode.{route}")
        assert action is not None, f"No mode-bar action for route {route!r}"
        action.trigger()
        qapp.processEvents()
        assert main_window.current_mode == route
        entry = {
            "presenter_instance": main_window.presenters[route],
            "view_instance": main_window.hosts[route].view,
        }

        return entry

    return _navigate
