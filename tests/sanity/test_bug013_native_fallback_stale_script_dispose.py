"""BUG-013 regression: a script-drawn indicator line registered against a
real native chart host, followed by a native->python fallback rebuild
(any `NativeUnsupportedFeatureError`, e.g. an out-of-scope script region),
left `IndicatorScriptRunner`'s dispose callback bound to the now-replaced,
`deleteLater()`'d native adapter. The next backtest run's
`clear_from_chart()` then invoked that stale dispose callback, crashing
deep inside `NativeBacktestChartHostAdapter.remove_indicator()` with a real
shiboken "C++ object already deleted" `RuntimeError`.

This is the exact same class of bug already fixed for
`_on_chart_mode_changed()` on 2026-08-18
(`test_switching_chart_mode_away_and_back_clears_stale_indicator_bookkeeping`
in `tests/unit/presentation/ui/screens/test_backtest_presenter.py`), just
reachable through the OTHER rebuild path
(`_fallback_to_python_after_unsupported_native_feature`) that fix didn't
touch.

Why this is a sanity test, not a unit test: the crash is inside
`NativeBacktestChartHost`'s own `_assert_owning_gui_thread()`, which reads
`self._widget.thread()` on a real `QQuickWidget`. A `Mock(spec=NativeBacktestChartHost)`
(as the existing unit-level fallback tests use) never executes that real
method body at all — it just records the call — so it structurally cannot
reproduce this crash. A real native host, constructed the same way
`test_backtest_native_chart_di_sanity.py` does, is required. This mirrors
exactly why BUG-013 was only ever found via real interactive use, not
existing test coverage.
"""

import os
from unittest.mock import patch

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
    NativeBacktestChartHostAdapter,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from shiboken6 import isValid


@pytest.fixture
def booted_app_with_native_chart_backend():
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )
    config_manager.load_dict({ConfigKeys.BACKTEST_CHART_BACKEND.value: "native"})

    app = create_app(config_manager)
    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app
        app.stop()


def _flush_deferred_delete() -> None:
    """Plain `QApplication.processEvents()` does NOT reliably flush a
    posted `DeferredDelete` event (verified empirically: an object stayed
    `isValid() == True` after 5 consecutive `processEvents()` calls in this
    environment). `sendPostedEvents(None, QEvent.DeferredDelete)` forces it
    directly, which is what actually makes the old native widget genuinely
    C++-deleted rather than merely orphaned in Python."""
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_native_fallback_clears_stale_script_runner_bookkeeping(
    qapp, booted_app_with_native_chart_backend, request
):
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    presenter = BackTestPresenter(
        view, booted_app_with_native_chart_backend.context.container
    )
    qapp.processEvents()

    native_card = view.chart_cards[0]
    assert isinstance(native_card, NativeBacktestChartHostAdapter)
    native_widget = native_card.native_host.widget
    assert isValid(native_widget)

    # Register a script-drawn overlay line against the REAL native host —
    # exactly what IndicatorScriptRunner.draw() does for a real user-picked
    # reference script, bypassing only the candle-feed pipeline (irrelevant
    # to this bug) by poking the runner's bookkeeping directly. Must call
    # add_overlay_indicator() for real (not just poke registered_lines) so
    # the adapter's _indicator_series has a real entry — otherwise
    # remove_indicator() is a no-op and never reaches the crash.
    import functools

    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.indicator_script_runner import (
        ActiveScript,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.script_region_tracker import (
        ScriptRegionTracker,
    )

    qualified = "test_script:R"
    native_card.add_overlay_indicator(qualified, "#8e44ad")
    active = ActiveScript(
        script=object(),  # never touched by clear_from_chart()
        overlay=True,
        region_tracker=ScriptRegionTracker(60.0),
    )
    active.registered_lines.add("R")
    active.scope.add(
        qualified, dispose=functools.partial(native_card.remove_indicator, qualified)
    )
    presenter._chart_script_runner.active["test_script"] = active

    # Triggers a real native -> python rebuild, exactly like an
    # out-of-scope script region would.
    presenter._fallback_to_python_after_unsupported_native_feature("script regions")
    python_card = view.chart_cards[0]
    assert python_card is not native_card

    # Force the old native card's deleteLater() to actually run, making
    # native_widget genuinely C++-deleted — the same state as the real bug
    # report, not merely orphaned in Python.
    _flush_deferred_delete()
    qapp.processEvents()
    assert not isValid(native_widget), (
        "test setup invalid: the old native widget was never actually "
        "C++-deleted, so this run cannot have exercised the real crash path"
    )

    # Reproduces the exact BUG-013 path: the next backtest run's
    # clear_from_chart() must not invoke the stale dispose callback still
    # pointed at the now-deleted native card. Must not raise.
    presenter._chart_script_runner.clear_from_chart(python_card)
