import os
from contextlib import suppress
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

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
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar import Sidebar
from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry
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
    # an engine and the Dev Board's auto-start has a worker running. Any
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

    # Loaded writable from a tmp copy, not the real file: Settings' Save
    # button calls ConfigManager.save(), and any test in this directory that
    # exercises it (directly or incidentally, e.g. by driving the full Dev
    # Board/Settings flow) must not overwrite the actual repo config on every
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

    # BOT-034: AutoStartController's fallback (default 2s — see
    # dashboard_presenter.py's _DEFAULT_AUTOSTART_FALLBACK_SECONDS) exists to
    # cover *real* wall-clock waiting for a live WS tick. This test module's
    # mocked dispatcher never produces one, and a single test's own setup +
    # waits reliably take close enough to 2 real seconds that the fallback
    # was firing *during* a test — submitting a second, independent
    # _load_history() background task that raced the test's own explicit
    # action against the same IndicatorScriptRunner/chart-card state. That
    # was a real, reproduced Windows access violation (bisected down to a
    # single, deterministically-crashing test with no other test involved).
    # Pushing the fallback out to effectively "never" here is honest test
    # isolation, not a workaround — the fallback's own timing behavior is
    # covered by tests/unit/.../test_autostart_controller.py, not by this
    # integration suite.
    config_manager.load_dict(
        {
            "DEV_BOARD_AUTOSTART_FALLBACK_SECONDS": 3600.0,
            "DEV_BOARD_AUTOSTART_ENABLED": True,
        }
    )

    engine = create_app(config_manager)

    def mock_dispatch(command_type, command_obj):
        # `ArmStrategyCommandHandler`/`DisarmStrategyCommandHandler` are run
        # for real rather than faked: `StrategyArmingCoordinator.armed_summary()`
        # reads its state from `LiveStrategySession.config`, which only the
        # real handler mutates — a fabricated `ArmStrategyResult(armed=True)`
        # would report success while leaving the session (and therefore the
        # card's own "what is armed" label) unchanged. Both handlers are
        # cheap, synchronous, and take only container-resolved collaborators,
        # so building them here costs nothing a `_FakeResponse` branch below
        # wouldn't already cost.
        if command_type is ArmStrategyCommandHandler:
            handler = ArmStrategyCommandHandler(
                engine.context.container.resolve(LiveStrategySession),
                engine.context.container.resolve(ITradingSession),
            )
            return handler.execute(command_obj)
        if command_type is DisarmStrategyCommandHandler:
            handler = DisarmStrategyCommandHandler(
                engine.context.container.resolve(LiveStrategySession),
                engine.context.container.resolve(ITradingSession),
            )
            return handler.execute(command_obj)
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
            handler = ExecuteOrderCommandHandler(
                engine.context.container.resolve(TradingVenue),
                engine.context.container.resolve(TradingSessionState),
                engine.context.container.resolve(ITradingAccountReader),
                engine.context.container.resolve(PreviewOrderQueryHandler),
                engine.context.container.resolve(TradingLimitPolicy),
                engine.context.container.resolve(ITradingSessionFactory),
                engine.context.container.resolve(IExchangeCredentialsProvider),
                engine.context.container.resolve(IMarketMetadataProvider),
            )
            return handler.execute(command_obj)
        if command_type is GetOpenPositionsQuery:
            # `GetOpenPositionsQueryHandler` itself builds a real
            # `FuturesTradingClient` and hits the network
            # (`get_positions()`) unconditionally — safe to do against a
            # real exchange/fake server (see
            # `test_manual_order_pipeline_against_fake_server.py`), but not
            # something this offscreen Qt suite's shared engine should do on
            # every manual-order click. `DashboardPresenter._run_manual_order`
            # only wants a real tuple shape back (it iterates `positions`
            # directly), not a network round trip, so a flat empty tuple —
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

    engine.stop()


@pytest.fixture
def main_window(qapp, qtbot, app_engine):
    """
    @brief Instantiate the MainWindow with the mocked engine.
    @details Teardown cancels every routed DashboardPresenter's
    _cancellation_token (BOT-034), stops its AutoStartController's pending
    fallback QTimer, and then blocks until this engine's IThreadManager pool
    has actually drained, before this fixture's own generator resumes —
    which, since fixtures tear down in reverse dependency order, happens
    *before* app_engine's teardown calls engine.stop(). Without this, a Load
    History/Start Live background task (or a fallback timer's later
    load_history call) left running past the end of a test can still be
    mid-emit when this test's Qt widgets get garbage-collected, touching an
    already-deleted pyqtgraph object — this was a real, reproduced crash
    (Windows access violation), not a hypothetical one.

    The fallback-timer piece matters independently of the cancellation
    token/thread-pool drain below: AutoStartController.begin() arms a
    2-second QTimer that only gets cancelled by a *real* MarketTickEvent
    (see on_market_tick) — the mocked dispatcher in this test module never
    produces one, so that timer is still armed when a test finishes in well
    under 2 seconds. Left alone, it fires *during a later test* (this is a
    single shared qapp/event loop across the whole file) and calls back into
    a presenter whose chart widgets are gone by then — this was the actual
    root cause of a crash that survived the cancellation-token/thread-pool
    fixes alone (verified by bisecting against the pre-autostart commit,
    which does not reproduce it at all).

    Cancelling the token only stops the NEXT checkpoint a background method
    reaches (cooperative, not a hard kill) — a bare sleep-based grace period
    was tried first and was NOT reliable (the crash still reproduced when
    combining test files, i.e. across an accumulation of orphaned timers/
    threads within one pytest process). thread_manager.shutdown(wait=True)
    is a hard guarantee instead of a probabilistic one: it blocks until
    every submitted task has actually returned. This is safe here
    specifically because DashboardPresenter's background tasks
    (_run_load_history / _run_sync_and_start) are bounded work (a few
    dispatch calls), not an indefinite loop — the real WS streaming loop
    lives elsewhere, outside this pool. Calling shutdown() again from
    ThreadManagerExtension during app_engine's own teardown afterward is
    safe — ThreadPoolExecutor.shutdown is idempotent. This is test-only
    teardown; production shutdown still deliberately uses wait=False (see
    thread_manager_module.py) since only this test fixture, not the app,
    needs to await widget-teardown safety.
    """
    registry = real_screen_registry(app_engine.context.container)
    window = MainWindow(app_engine, registry, sidebar_factory=Sidebar)
    window.show()
    yield window
    for entry in window._router._registry.values():
        presenter = entry.get("presenter_instance")
        autostart = getattr(presenter, "_autostart", None)
        if autostart is not None:
            autostart.shutdown()
        token = getattr(presenter, "_cancellation_token", None)
        if token is not None:
            token.cancel()

    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    thread_manager = app_engine.context.container.resolve(IThreadManager)
    if thread_manager is not None:
        thread_manager.shutdown(wait=True)

    # ChartCard.viewport/zoom_controls/crosshair are plain QObjects
    # constructed with no C++ parent (see ViewportController.__init__) — an
    # event filter registered via installEventFilter() is a raw pointer on
    # the filtered widget's side, not a Qt-managed ownership link. Normally
    # ChartCard.cleanup() explicitly disposes them (see
    # DashboardView.render_symbol_cards, which calls it every time it
    # replaces the current cards). But _ensure_chart_cards reuses the same
    # cards for the lifetime of one Dev Board screen (symbols never change
    # within a test), so cleanup() is otherwise never called for whichever
    # cards are still current when a test ends — leaving Qt's normal
    # deleteLater()-driven widget teardown to destroy `canvas` out from
    # under a still-alive ViewportController, or vice versa, with no
    # guaranteed ordering. Whichever side survives longer is left holding a
    # dangling event-filter pointer to the other — a real, reproduced
    # Windows access violation (bisected: does not reproduce before
    # BOT-034's auto-start, which is what pushed every Dev Board test to
    # actually construct chart cards instead of only some of them).
    for entry in window._router._registry.values():
        view = entry.get("view_instance")
        cards = getattr(view, "chart_cards", None)
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
    Clicks a sidebar entry the way a user would and returns that route's
    router registry entry (which holds the lazily-created view/presenter).

    The sidebar is plain QtWidgets (EPIC-006C) — navigation goes through
    `Sidebar._nav_buttons[route]`'s real `QPushButton.click()`.
    Centralized here so every screen test shares one implementation
    instead of repeating the item lookup.
    """

    def _navigate(route: str) -> dict:
        button = main_window._sidebar._nav_buttons.get(route)
        assert button is not None, f"No sidebar nav button for route {route!r}"
        button.click()
        qapp.processEvents()
        entry = main_window._router._registry[route]

        # BOT-034: opening the Dev Board auto-starts Start Live — a real
        # background task on this fixture's real ThreadPoolExecutor (see
        # app_engine's docstring). Waiting here for it to settle (success or
        # failure) is not optional politeness: without it, the task can
        # still be mid-flight touching the chart when a test finishes and
        # main_window's Qt widgets get torn down, which reliably produced a
        # real crash (Windows access violation in a ThreadPoolExecutor
        # worker touching an already-deleted pyqtgraph ViewBox) before this
        # wait was added. Best-effort: a second navigate("dashboard") in the
        # same test reuses the already-settled presenter, so there is
        # nothing new to wait for — swallow the timeout rather than fail.
        presenter = entry.get("presenter_instance")
        if route == "dashboard" and presenter is not None:
            settled = {"done": False}

            def _mark_settled(*_args) -> None:
                settled["done"] = True

            presenter.ui_stream_success_signal.connect(_mark_settled)
            presenter.ui_stream_failed_signal.connect(_mark_settled)
            with suppress(Exception):
                qtbot.waitUntil(lambda: settled["done"], timeout=2000)

        return entry

    return _navigate
