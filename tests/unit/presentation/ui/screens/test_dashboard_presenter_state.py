"""`EPIC-010D` — the Dev Board remembers symbol, interval, and how far back
its date window reaches.

Kept out of `test_dashboard_presenter.py` (already 1200+ lines) and given its
own compact fixtures rather than importing that file's: these tests need a
container that *does* register a `UiStateCoordinator`, which that file's
`mock_container` deliberately does not.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DATETIME_FORMAT,
    DEFAULT_LOOKBACK_DAYS,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_SCOPE = StateScope(key="dashboard")


@pytest.fixture
def dispatcher():
    return MagicMock()


@pytest.fixture
def container(dispatcher):
    """Mirrors `test_dashboard_presenter.py`'s container in the parts that
    matter here: a key-aware config (a blanket stub makes AutoStartController's
    fallback timer fire almost immediately — see that file's own note), and
    `dev.mode` on so a `@safe_ui_action` slot re-raises instead of quietly
    swallowing a failure this suite should see."""
    config = MagicMock()
    config.get.side_effect = lambda key, default=None, cast=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    config.get_all.return_value = {}

    registry = IndicatorScriptRegistry()

    resolved = {
        IConfig: config,
        IDispatcher: dispatcher,
        IThreadManager: MagicMock(),
        IndicatorScriptRegistry: registry,
    }

    c = MagicMock()
    c.resolve.side_effect = lambda interface: resolved.get(interface, MagicMock())
    c.registrations.return_value = {}
    return c


@pytest.fixture
def view(qapp):
    v = DashboardView()
    v.resize(1200, 800)
    return v


def _with_coordinator(container, coordinator):
    """Registers `coordinator` the way `app_bootstrapper.build()` does."""
    container.registrations.return_value = {UiStateCoordinator: object()}
    plain_resolve = container.resolve.side_effect

    def resolve(interface):
        if interface is UiStateCoordinator:
            return coordinator
        return plain_resolve(interface)

    container.resolve.side_effect = resolve
    return container


def _coordinator_with(slice_data: dict | None = None) -> UiStateCoordinator:
    store = InMemoryStateStore()
    if slice_data is not None:
        store.write(_SCOPE, slice_data)
    return UiStateCoordinator(store, debounce_ms=50_000)  # flush() drives writes


def _lookback_days_on(presenter) -> int:
    vm = presenter._view_model
    start = datetime.strptime(vm.startDate, DATETIME_FORMAT).replace(tzinfo=UTC)
    end = datetime.strptime(vm.endDate, DATETIME_FORMAT).replace(tzinfo=UTC)
    return (end - start).days


def test_works_unchanged_when_no_coordinator_is_registered(view, container):
    """Backward compatibility: every existing test builds a presenter against
    a container with nothing registered, and production did too before
    `app_bootstrapper` was wired."""
    presenter = DashboardPresenter(view, container)

    assert presenter._state_coordinator is None
    assert presenter._view_model.symbol == "ETHUSDT"
    assert presenter._active_interval == "1m"


def test_restores_symbol_interval_and_lookback_from_a_prior_session(view, container):
    coordinator = _coordinator_with(
        {"symbol": "BTCUSDT", "interval": "5m", "lookback_days": 3}
    )

    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    assert presenter._view_model.symbol == "BTCUSDT"
    assert presenter._active_interval == "5m"
    assert _lookback_days_on(presenter) == 3


def test_restoring_never_fetches_anything(view, container, dispatcher):
    """Mode #12 / D6, and the acceptance criterion this task was written
    around: opening the app pre-fills the form and nothing else. A restore
    that looked like the user acting would reach a handler and start a
    fetch."""
    coordinator = _coordinator_with(
        {"symbol": "BTCUSDT", "interval": "15m", "lookback_days": 2}
    )

    DashboardPresenter(view, _with_coordinator(container, coordinator))

    assert dispatcher.dispatch.call_count == 0


def test_a_restore_does_not_immediately_write_itself_back(view, container):
    """Restoring is not a user edit, so it must not leave the slice dirty —
    otherwise every launch rewrites the file for no reason, and a value the
    user never touched gets a fresh timestamp on disk."""
    coordinator = _coordinator_with({"symbol": "BTCUSDT", "interval": "5m"})

    DashboardPresenter(view, _with_coordinator(container, coordinator))

    assert coordinator._dirty == {}


def test_an_implausible_symbol_falls_back_without_discarding_the_interval(
    view, container
):
    """D5, and the reason each field is validated on its own: a symbol that
    no longer parses must not take a perfectly good interval down with it."""
    coordinator = _coordinator_with({"symbol": "!!! not a symbol", "interval": "4h"})

    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    assert presenter._view_model.symbol == "ETHUSDT"
    assert presenter._active_interval == "4h"


def test_an_interval_that_is_no_longer_a_timeframe_falls_back(view, container):
    coordinator = _coordinator_with({"symbol": "BTCUSDT", "interval": "7q"})

    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    assert presenter._active_interval == "1m"
    assert presenter._view_model.symbol == "BTCUSDT"


@pytest.mark.parametrize(
    "stored",
    [
        {},
        {"lookback_days": 0},
        {"lookback_days": -5},
        {"lookback_days": "seven"},
        {"lookback_days": True},  # bool is an int subclass — must not pass
        {"lookback_days": 999_999},
    ],
    ids=["absent", "zero", "negative", "text", "bool", "absurd"],
)
def test_a_missing_or_nonsense_lookback_keeps_todays_behaviour(view, container, stored):
    coordinator = _coordinator_with(stored)

    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    assert _lookback_days_on(presenter) == DEFAULT_LOOKBACK_DAYS


def test_dates_are_captured_as_a_duration_not_as_timestamps(view, container):
    """Risk R2: an absolute window remembered from a month ago would make the
    next Load History fetch an enormous range. What lands on disk is a day
    count, and no date string at all."""
    coordinator = _coordinator_with()
    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    captured = presenter.capture_state()

    assert captured["lookback_days"] == DEFAULT_LOOKBACK_DAYS
    assert "startDate" not in captured
    assert "endDate" not in captured
    assert not any(
        isinstance(value, str) and "-" in value and ":" in value
        for value in captured.values()
    )


def test_a_restored_duration_is_recomputed_against_todays_clock(view, container):
    """The point of storing a duration: the window always ends now, however
    long the app sat unused."""
    coordinator = _coordinator_with({"lookback_days": 4})

    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    end = datetime.strptime(presenter._view_model.endDate, DATETIME_FORMAT).replace(
        tzinfo=UTC
    )
    assert abs((datetime.now(UTC) - end).total_seconds()) < 120


def test_changing_the_symbol_survives_a_restart(view, container, qapp):
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store, debounce_ms=50_000)
    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    presenter._view_model.symbol = "SOLUSDT"  # what the combo's handler does
    coordinator.flush()

    assert store.read(_SCOPE)["symbol"] == "SOLUSDT"


def test_changing_the_timeframe_survives_a_restart(view, container):
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store, debounce_ms=50_000)
    presenter = DashboardPresenter(view, _with_coordinator(container, coordinator))

    presenter._on_timeframe_changed("15m")  # what ChartToolbar emits
    coordinator.flush()

    assert store.read(_SCOPE)["interval"] == "15m"
