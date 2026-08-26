"""`EPIC-010E` — the Database screen remembers its symbol and interval.

Kept out of `test_data_management_presenter.py` and given its own fixtures for
the same reason `test_dashboard_presenter_state.py` is separate: these tests
need a container that *does* register a `UiStateCoordinator`, and that file's
does not.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
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

_SCOPE = StateScope(key="data_management")


@pytest.fixture
def thread_manager():
    return Mock()


@pytest.fixture
def dispatcher():
    return Mock()


@pytest.fixture
def container(thread_manager, dispatcher):
    config = Mock()
    config.get_all.return_value = {}
    config.get.side_effect = lambda key, default=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )

    resolved = {
        IThreadManager: thread_manager,
        IDispatcher: dispatcher,
        IConfig: config,
    }

    c = Mock()
    c.resolve.side_effect = lambda interface: resolved.get(interface, Mock())
    c.registrations.return_value = {}
    return c


@pytest.fixture
def view(qapp, request):
    v = DataManagementView()
    v.resize(1400, 800)
    request.addfinalizer(v.deleteLater)
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


def test_works_unchanged_when_no_coordinator_is_registered(view, container):
    presenter = DataManagementPresenter(view, container)

    assert presenter._state_coordinator is None
    assert presenter._view_model.selectedSymbol == "BTCUSDT"


def test_restores_symbol_and_interval_from_a_prior_session(view, container):
    coordinator = _coordinator_with({"symbol": "SOLUSDT", "interval": "4h"})

    presenter = DataManagementPresenter(view, _with_coordinator(container, coordinator))

    assert presenter._view_model.selectedSymbol == "SOLUSDT"
    assert presenter._view_model.selectedInterval == "4h"


def test_restoring_neither_scans_nor_syncs(view, container, dispatcher):
    """Mode #12, and this task's own acceptance criterion: opening the screen
    pre-fills the form. The one background task it submits on open is its
    normal auto-discovery, which happens with or without a restore — what must
    not appear is a dispatch on the main thread caused by restoring."""
    coordinator = _coordinator_with({"symbol": "ETHUSDT", "interval": "1h"})

    DataManagementPresenter(view, _with_coordinator(container, coordinator))

    assert dispatcher.dispatch.call_count == 0


def test_a_restore_does_not_immediately_write_itself_back(view, container):
    coordinator = _coordinator_with({"symbol": "ETHUSDT", "interval": "1h"})

    DataManagementPresenter(view, _with_coordinator(container, coordinator))

    assert coordinator._dirty == {}


def test_a_symbol_absent_from_the_options_falls_back_without_losing_the_interval(
    view, container
):
    """The wrinkle this screen has and the Dev Board does not: `symbolOptions`
    is replaced at runtime by DB auto-discovery, so a remembered symbol can
    simply not be there. It must fall back quietly — and must not drag the
    interval down with it."""
    coordinator = _coordinator_with({"symbol": "DOGEUSDT", "interval": "12h"})

    presenter = DataManagementPresenter(view, _with_coordinator(container, coordinator))

    assert presenter._view_model.selectedSymbol == "BTCUSDT"
    assert presenter._view_model.selectedInterval == "12h"


def test_an_interval_that_is_not_a_known_timeframe_falls_back(view, container):
    coordinator = _coordinator_with({"symbol": "ETHUSDT", "interval": "7q"})

    presenter = DataManagementPresenter(view, _with_coordinator(container, coordinator))

    assert presenter._view_model.selectedInterval == "1s"  # _SUPPORTED_INTERVALS[0]
    assert presenter._view_model.selectedSymbol == "ETHUSDT"


@pytest.mark.parametrize(
    "stored",
    [{}, {"symbol": None}, {"symbol": 123, "interval": []}],
    ids=["empty", "null-symbol", "wrong-types"],
)
def test_a_missing_or_malformed_slice_leaves_the_defaults_alone(
    view, container, stored
):
    coordinator = _coordinator_with(stored)

    presenter = DataManagementPresenter(view, _with_coordinator(container, coordinator))

    assert presenter._view_model.selectedSymbol == "BTCUSDT"
    assert presenter._view_model.selectedInterval == "1s"


def test_changing_the_selection_survives_a_restart(view, container):
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store, debounce_ms=50_000)
    presenter = DataManagementPresenter(view, _with_coordinator(container, coordinator))

    presenter._view_model.selectedSymbol = "XRPUSDT"
    presenter._view_model.selectedInterval = "1d"
    coordinator.flush()

    assert store.read(_SCOPE) == {"symbol": "XRPUSDT", "interval": "1d"}
