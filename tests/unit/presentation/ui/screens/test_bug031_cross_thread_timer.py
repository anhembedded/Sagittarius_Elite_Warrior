"""
Regression test for BUG-031:
Cross-thread timer start and UI layout hang during Backtest.

Root cause (original QML-era bug):
In BackTestView._bind_top_panel_height(), `root.implicitHeightChanged` was connected
to a local closure `sync_height` which directly called `QTimer.singleShot(0, apply_height)`.
When implicitHeightChanged is triggered as a result of cross-thread property changes
or worker thread notifications, `sync_height` runs on that worker thread where
QTimer.singleShot fails with:
"QBasicTimer::start: Timers cannot be started from another thread"
leaving `resize_pending` stuck at True and causing layout/event freezes.

EPIC-006E1 deleted `_bind_top_panel_height()` entirely — `BackTestTopPanel`
is plain QtWidgets now, sized by its own layout, with no
`implicitHeightChanged` QML signal to connect to — so the specific
cross-thread-signal regression this guarded against is no longer
structurally possible; only the unrelated `set_ui_mode` slot-decorator
assertion below still applies and is kept.

Furthermore, BackTestViewModel.set_ui_mode was overriding the base class without
the `@Slot(str)` decorator.
"""

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import unprotected_mutators


def test_backtest_view_model_set_ui_mode_has_slot_decorator():
    """Confirms all BackTestViewModel mutators including set_ui_mode are protected with @Slot."""
    unprotected = unprotected_mutators(BackTestViewModel)
    assert "set_ui_mode" not in unprotected
    assert unprotected == []
