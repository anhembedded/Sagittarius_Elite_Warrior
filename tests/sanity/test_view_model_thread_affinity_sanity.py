"""
Layer 1 sanity test (BOT-068, engine "lớp lỗi A" — see
Tasks/reports/engine_defect_class_analysis.md): every public mutator-shaped
method (`set_*`/`append*`/`clear*`/`hide_*`) on every `BaseQmlViewModel`
subclass in this app must be protected by `@Slot` or `@ui_mutator` — the
class BUG-001 was, a background thread calling a ViewModel method directly,
bypassing signals entirely, went undetected until a QML `Behavior on width`
animation happened to need a `QTimer` and Qt6 crashed the app rather than
let it start from the wrong thread.

Pure class-level introspection via `sagittarius_engine`'s
`unprotected_mutators()` (see its own docstring) — no app boot, no QML, no
DI container needed. Deliberately does NOT use `vars(cls)` only, so a
mutator inherited from `BaseQmlViewModel` itself (e.g. `set_ui_mode`) is
caught too, not just ones each screen defines directly.
"""

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view_model import (
    SettingsViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_view_model import (
    TradingViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import unprotected_mutators

#: Every `BaseQmlViewModel` subclass this app ships. A screen missing from
#: this list would silently escape the guard, so
#: `test_every_view_model_subclass_in_this_app_is_covered_by_this_list`
#: below pins the count against a live scan, not just this hand-written list.
_ALL_VIEW_MODELS = [
    BackTestViewModel,
    DashboardQmlViewModel,
    DataManagementViewModel,
    SettingsViewModel,
    TradingViewModel,
]


@pytest.mark.parametrize(
    "view_model_cls", _ALL_VIEW_MODELS, ids=lambda cls: cls.__name__
)
def test_every_view_model_mutator_is_protected_from_cross_thread_calls(
    view_model_cls,
) -> None:
    unprotected = unprotected_mutators(view_model_cls)

    assert unprotected == [], (
        f"{view_model_cls.__name__} has mutator(s) with no @Slot/@ui_mutator "
        f"protection, callable directly from a background thread: {unprotected}"
    )


_PRODUCTION_MODULE_PREFIX = "Sagittarius_Elite_Warrior.src."


def test_every_view_model_subclass_in_this_app_is_covered_by_this_list() -> None:
    """Guards `_ALL_VIEW_MODELS` itself against drift — a new screen's
    ViewModel added later but never added here would make the test above
    silently stop meaning anything for it.

    Filters to classes defined under `Sagittarius_Elite_Warrior.src.` —
    running the full suite, `BaseQmlViewModel.__subclasses__()` also picks up
    test-only doubles other test files define for their own purposes (e.g.
    test_shared_ui_state_foundation.py's `_ProbeViewModel`, a local class
    inside one test function, used only to exercise the FSM/uiMode wiring
    mechanism generically) — those aren't screens this app ships and have
    nothing to do with this scan."""
    from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel

    def all_subclasses(cls: type) -> set[type]:
        direct = set(cls.__subclasses__())
        return direct | {s for c in direct for s in all_subclasses(c)}

    discovered = {
        cls
        for cls in all_subclasses(BaseQmlViewModel)
        if cls.__module__.startswith(_PRODUCTION_MODULE_PREFIX)
    }
    assert discovered == set(_ALL_VIEW_MODELS), (
        f"_ALL_VIEW_MODELS is out of sync with what's actually defined — "
        f"missing: {discovered - set(_ALL_VIEW_MODELS)}, "
        f"stale: {set(_ALL_VIEW_MODELS) - discovered}"
    )
