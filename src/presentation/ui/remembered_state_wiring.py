"""What the shell remembers between runs, registered once at start-up.

@details Split out of `app_bootstrapper.build()` (a known god file that may only
shrink, `architecture-rule.md` §5.4): the coordinator itself is constructed
there, after `QApplication` exists, because it owns a `QTimer`; everything that
is *registered* on it and on the container is here. Behaviour and order are
unchanged.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.charting.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
)
from sagittarius_engine.interfaces.i_container import IContainer


def register_remembered_state(
    container: IContainer, state_coordinator: UiStateCoordinator
) -> None:
    # Registered so screen presenters can find it: PresenterManager builds
    # each presenter as `presenter_class(view, container)`, with no seam for
    # extra constructor arguments, so the container is the only way through.
    # A presenter must therefore treat it as optional — every test that
    # builds a presenter against a bare container would otherwise break.
    container.singleton(UiStateCoordinator, state_coordinator)

    # EPIC-017A — which screens' remembered fields Settings' DEFAULT_SYMBOLS/
    # DEFAULT_INTERVAL outrank (EPIC-010H's ui_state > user_config
    # precedence). Registered here, eagerly, rather than inside each
    # presenter's own __init__: PresenterManager is a *true* lazy router (see
    # its own docstring — "zero RAM allocation for screens until navigated
    # to"), so a binding registered only when a presenter is first
    # constructed would silently miss a screen the user has never opened yet
    # — the exact stale-restore bug this registration exists to prevent.
    # Plain strings on purpose: this is the composition root, the one place
    # already allowed to know every screen's route (see MainWindow's own
    # router setup) — importing each screen's heavy presenter module just to
    # read its scope/field names would defeat the lazy loading above for no
    # benefit, since nothing here needs the class itself.
    for scope_key, config_key, state_keys in (
        ("backtest", "DEFAULT_SYMBOLS", ("symbol",)),
        ("backtest", "DEFAULT_INTERVAL", ("timeframe",)),
        ("data_management", "DEFAULT_SYMBOLS", ("symbol",)),
        ("data_management", "DEFAULT_INTERVAL", ("interval",)),
    ):
        state_coordinator.register_config_binding(
            StateScope(key=scope_key), config_key, state_keys
        )

    # EPIC-014 — starred and recently used trading pairs, ONE store shared by
    # every screen that picks a symbol. Registered rather than owned by a
    # screen because that is what makes it shared: a star set on Backtest is
    # the same star every other picker shows, which is the whole reason favourites are
    # worth having across a 1,400-entry list.
    #
    # Restored before the first screen is built and marked dirty on every
    # mutation: the two calls every contributor makes, here as it has no presenter.
    symbol_preferences = SymbolPreferences()
    state_coordinator.restore_into(symbol_preferences)
    symbol_preferences.set_on_changed(
        lambda: state_coordinator.mark_dirty(symbol_preferences)
    )
    container.singleton(SymbolPreferences, symbol_preferences)

    # Follow-up to `EPIC-015` Phase 4 — pinned timeframes per chart, keyed by
    # symbol, shared by every `ChartToolbar` in the app the same way
    # `SymbolPreferences` is shared above: Backtest's single chart and each
    # other `ChartCard` read the same store, scoped by their own symbol,
    # so a chart rebuilt for a symbol it has already seen recovers the same
    # pinned set instead of resetting it.
    timeframe_pin_preferences = TimeframePinPreferences()
    state_coordinator.restore_into(timeframe_pin_preferences)
    timeframe_pin_preferences.set_on_changed(
        lambda: state_coordinator.mark_dirty(timeframe_pin_preferences)
    )
    container.singleton(TimeframePinPreferences, timeframe_pin_preferences)
