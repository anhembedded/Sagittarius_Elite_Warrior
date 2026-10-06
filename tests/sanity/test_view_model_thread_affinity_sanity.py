"""
Layer 1 sanity test (BOT-068, engine "lớp lỗi A" — see
Tasks/reports/engine_defect_class_analysis.md): every public mutator-shaped
method (`set_*`/`append*`/`clear*`/`hide_*`) on every screen ViewModel this
app derives from its two bases, `UiModeViewModel` and `StatusMessageViewModel`, must be protected by `@Slot` or `@ui_mutator` — the
class BUG-001 was, a background thread calling a ViewModel method directly,
bypassing signals entirely, went undetected until a QML `Behavior on width`
animation happened to need a `QTimer` and Qt6 crashed the app rather than
let it start from the wrong thread.

Pure class-level introspection via `sagittarius_engine`'s
`unprotected_mutators()` (see its own docstring) — no app boot, no QML, no
DI container needed. Deliberately does NOT use `vars(cls)` only, so a
mutator inherited from a base (e.g. `UiModeViewModel.set_ui_mode`) is
caught too, not just ones each screen defines directly.
"""

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_view_model import (
    MarketDataSettingsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view_model import (
    DeskViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view_model import (
    TradingSettingsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.ui_mode_view_model import (
    UiModeViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import unprotected_mutators

#: Every screen ViewModel this app ships on its two bases, and the bases. A screen missing from
#: this list would silently escape the guard, so
#: `test_every_view_model_subclass_in_this_app_is_covered_by_this_list`
#: below pins the count against a live scan, not just this hand-written list.
#:
#: `EPIC-025E` PR 4.4e retired `SettingsViewModel` (split into
#: `TradingSettingsViewModel`/`MarketDataSettingsViewModel`) and added
#: `StatusMessageViewModel` — the shared base both of those and
#: `DeskViewModel` now subclass for their status-message trio,
#: extracted per `test_presenter_duplication_only_shrinks.py`'s own ratchet.
#: It ships its own `@Slot`-protected `set_status()`, so it belongs in this
#: list like any other ViewModel this app defines. `BUG-152` moved all of
#: them off the Engine's `BaseQmlViewModel`: `UiModeViewModel` carries the
#: same `set_ui_mode` contract without a `QtCore.Property`.
_ALL_VIEW_MODELS = [
    BackTestViewModel,
    DataManagementViewModel,
    MarketDataSettingsViewModel,
    StatusMessageViewModel,
    TradingSettingsViewModel,
    UiModeViewModel,
    DeskViewModel,
    BotsViewModel,
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


#: The bases a screen ViewModel derives from; a subclass of either is found.
_VIEW_MODEL_BASES = (UiModeViewModel, StatusMessageViewModel)


def test_every_view_model_subclass_in_this_app_is_covered_by_this_list() -> None:
    """Guards `_ALL_VIEW_MODELS` itself against drift — a new screen's
    ViewModel added later but never added here would make the test above
    silently stop meaning anything for it.

    Filters to classes defined under `Sagittarius_Elite_Warrior.src.`: the
    full suite also defines test-only subclasses of these bases (a local
    probe inside one test function), which are not screens this app ships."""

    def all_subclasses(cls: type) -> set[type]:
        direct = set(cls.__subclasses__())
        return direct | {s for c in direct for s in all_subclasses(c)}

    discovered = {
        cls
        for base in _VIEW_MODEL_BASES
        for cls in {base} | all_subclasses(base)
        if cls.__module__.startswith(_PRODUCTION_MODULE_PREFIX)
    }
    assert discovered == set(_ALL_VIEW_MODELS), (
        f"_ALL_VIEW_MODELS is out of sync with what's actually defined — "
        f"missing: {discovered - set(_ALL_VIEW_MODELS)}, "
        f"stale: {set(_ALL_VIEW_MODELS) - discovered}"
    )
