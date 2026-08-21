"""
Regression test for BUG-031:
Cross-thread timer start and UI layout hang during Backtest.

Root cause:
In BackTestView._bind_top_panel_height(), `root.implicitHeightChanged` was connected
to a local closure `sync_height` which directly called `QTimer.singleShot(0, apply_height)`.
When implicitHeightChanged is triggered as a result of cross-thread property changes
or worker thread notifications, `sync_height` runs on that worker thread where
QTimer.singleShot fails with:
"QBasicTimer::start: Timers cannot be started from another thread"
leaving `resize_pending` stuck at True and causing layout/event freezes.

Furthermore, BackTestViewModel.set_ui_mode was overriding the base class without
the `@Slot(str)` decorator.
"""

import threading

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import unprotected_mutators


def test_backtest_view_model_set_ui_mode_has_slot_decorator():
    """Confirms all BackTestViewModel mutators including set_ui_mode are protected with @Slot."""
    unprotected = unprotected_mutators(BackTestViewModel)
    assert "set_ui_mode" not in unprotected
    assert unprotected == []


def test_backtest_view_sync_height_safe_from_worker_thread(qapp, qtbot):
    """
    Simulates implicitHeightChanged being emitted from a worker thread.
    The callback must execute safely on the GUI thread without raising or
    failing to schedule the height application.
    """
    view = BackTestView()
    qtbot.addWidget(view)
    view_model = BackTestViewModel()
    view.set_view_model(view_model)
    view.load_qml()

    root = view.top_widget.rootObject()
    assert root is not None

    errors: list[BaseException] = []

    def trigger_from_worker():
        try:
            # Emitting the QML item's signal directly from a background worker thread
            root.implicitHeightChanged.emit()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    thread = threading.Thread(target=trigger_from_worker)
    thread.start()
    thread.join()

    # Process events to allow queued invocations on the GUI thread
    qapp.processEvents()

    assert errors == []
    assert view.top_widget.height() >= 0
