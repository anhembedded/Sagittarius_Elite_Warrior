"""`EPIC-010F` — the Backtest screen remembers its whole configuration form.

Separate from `test_backtest_presenter.py` for the same reason the `010D`/`010E`
state suites are separate: these need a container that *does* register a
`UiStateCoordinator`, and that file's does not.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import (
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_state_fields import (
    BACKTEST_STATE_FIELDS,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
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

_SCOPE = StateScope(key="backtest")


class _FakeStrategy(BaseStrategy):
    """Mirrors `test_backtest_presenter.py`'s own fake. Registered rather
    than left empty because an empty registry means an empty
    `strategyOptions`, and then `selectedStrategyKey` has no valid value to
    hold — an artificial state no real app is ever in."""

    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


@pytest.fixture
def dispatcher():
    return Mock()


@pytest.fixture
def strategy_registry():
    registry = StrategyRegistry()
    registry.register("fake_strategy", _FakeStrategy)
    return registry


@pytest.fixture
def container(dispatcher, strategy_registry):
    config = Mock()
    config.get_all.return_value = {}
    config.get.side_effect = lambda key, default=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )

    resolved = {
        IThreadManager: Mock(),
        IDispatcher: dispatcher,
        IConfig: config,
        StrategyRegistry: strategy_registry,
        IndicatorScriptRegistry: IndicatorScriptRegistry(),
        BacktestChartHostFactory: BacktestChartHostFactory(),
    }

    c = Mock()
    c.resolve.side_effect = lambda interface: resolved.get(interface, Mock())
    c.registrations.return_value = {}
    return c


@pytest.fixture
def view(qapp, request):
    v = BackTestView()
    v.resize(1400, 800)
    request.addfinalizer(v.deleteLater)
    return v


def _with_coordinator(container, coordinator):
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
    presenter = BackTestPresenter(view, container)

    assert presenter._state_coordinator is None


def test_every_declared_field_round_trips(view, container):
    """The table is the contract: whatever `capture_state()` writes,
    `restore_state()` must take back. Driven off `BACKTEST_STATE_FIELDS` rather
    than a hand-listed set of keys, so a field added to the table without a
    working round trip fails here instead of being quietly half-wired."""
    coordinator = _coordinator_with()
    presenter = BackTestPresenter(view, _with_coordinator(container, coordinator))

    captured = presenter.capture_state()

    assert set(captured) == {field.key for field in BACKTEST_STATE_FIELDS}
    # Every captured value must survive its own validator — otherwise the
    # screen cannot restore what it just wrote.
    for field in BACKTEST_STATE_FIELDS:
        assert field.is_valid(captured[field.key], presenter._view_model), field.key


def test_restores_a_whole_remembered_form(view, container):
    stored = {
        "capital": "12345",
        "currency": "USDT",
        "execution_mode": "tick",
        "order_size_type": "fixed_cash",
        "order_size": "250",
        "pyramiding": 3,
        "commission_type": "cash_per_order",
        "commission": "1.5",
        "slippage_ticks": 7,
        "long_leverage": 2.5,
        "short_leverage": 1.5,
        "take_profit_enabled": True,
        "take_profit_pct": "4.2",
        "time_range_preset": "last_30_days",
        "custom_start": "2024-01-01 00:00",
        "custom_end": "2024-02-01 00:00",
        "extended_metrics": True,
    }
    coordinator = _coordinator_with(stored)

    presenter = BackTestPresenter(view, _with_coordinator(container, coordinator))
    vm = presenter._view_model

    assert vm.initialCapitalText == "12345"
    assert vm.pyramiding == 3
    assert vm.slippageTicks == 7
    assert vm.longLeverage == 2.5
    assert vm.takeProfitPctEnabled is True
    assert vm.customStartText == "2024-01-01 00:00"
    assert vm.showExtendedMetrics is True


def test_restoring_never_runs_anything(view, container, dispatcher):
    """Mode #12 and this task's acceptance criterion: opening the screen
    pre-fills the form and nothing else — no backtest, no sync, no fetch."""
    coordinator = _coordinator_with({"capital": "999", "pyramiding": 4})

    BackTestPresenter(view, _with_coordinator(container, coordinator))

    assert dispatcher.dispatch.call_count == 0


def test_a_restore_does_not_immediately_write_itself_back(view, container):
    coordinator = _coordinator_with({"capital": "777"})

    BackTestPresenter(view, _with_coordinator(container, coordinator))

    assert coordinator._dirty == {}


@pytest.mark.parametrize(
    ("key", "bad_value"),
    [
        ("pyramiding", 0),
        ("pyramiding", True),  # bool is an int subclass — must not pass
        ("slippage_ticks", -1),
        ("long_leverage", 10_000),
        ("currency", "NOT_A_CURRENCY"),
        ("commission_type", "barter"),
        ("time_range_preset", "since_forever"),
        ("execution_mode", "telepathy"),
        ("take_profit_enabled", "yes"),
        ("capital", "x" * 500),
    ],
)
def test_one_bad_field_falls_back_alone(view, container, key, bad_value):
    """D5, and the reason each row carries its own predicate: a corrupt value
    must not take the rest of the form down with it."""
    good = {"pyramiding": 5, "capital": "4321", "extended_metrics": True}
    stored = {**good, key: bad_value}
    coordinator = _coordinator_with(stored)

    presenter = BackTestPresenter(view, _with_coordinator(container, coordinator))
    vm = presenter._view_model

    for good_key, good_value in good.items():
        if good_key == key:
            continue
        field = next(f for f in BACKTEST_STATE_FIELDS if f.key == good_key)
        assert getattr(vm, field.prop) == good_value, (
            f"{good_key} should still restore despite {key} being invalid"
        )


def test_symbol_and_timeframe_are_deliberately_not_remembered(view, container):
    """Scope decision, not an oversight: they are the only two values where
    Settings' DEFAULT_* keys would also claim the field, and settling that
    precedence is EPIC-010H. See the task file."""
    keys = {field.key for field in BACKTEST_STATE_FIELDS}
    props = {field.prop for field in BACKTEST_STATE_FIELDS}

    assert "symbol" not in keys
    assert "timeframe" not in keys
    assert "selectedSymbol" not in props
    assert "selectedTimeframe" not in props


def test_editing_a_field_survives_a_restart(view, container):
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store, debounce_ms=50_000)
    presenter = BackTestPresenter(view, _with_coordinator(container, coordinator))

    presenter._view_model.initialCapitalText = "55555"
    presenter._view_model.pyramiding = 6
    coordinator.flush()

    written = store.read(_SCOPE)
    assert written["capital"] == "55555"
    assert written["pyramiding"] == 6


def test_every_field_has_the_notifier_the_debounce_relies_on(view, container):
    """`_connect_state_tracking()` derives `<prop>Changed` by convention. If a
    ViewModel rename ever broke that, the field would silently stop being
    persisted — so the convention is asserted rather than assumed."""
    presenter = BackTestPresenter(view, container)

    for field in BACKTEST_STATE_FIELDS:
        assert hasattr(presenter._view_model, f"{field.prop}Changed"), field.prop
