"""`BOT-144` — `DashboardPresenter`'s active-interval/symbol state and its
custom indicator-script infrastructure (registry, catalog, params store,
runner, `IndicatorCoordinator`). Split out of `presenter_factory.py` once
that file itself crossed the 400-line ceiling (`architecture-rule.md` §5.4)
— see that file's own docstring for why this whole construction sequence is
a Builder over `presenter`, not an independent-object Factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
    IndicatorScriptParamsStore,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.runner import (
    IndicatorScriptRunner,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL,
    default_interval,
    default_symbol,
)

from ..coordinators.indicator_coordinator import IndicatorCoordinator

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from ..dashboard_presenter import DashboardPresenter


def build_indicator_presenter_state(
    presenter: DashboardPresenter, container: IContainer
) -> None:
    """`_active_interval`/`_active_symbol`, the indicator-script registry/
    catalog/params-store/runner, and `IndicatorCoordinator`. Call third, from
    `build_dashboard_presenter_state()` only, after
    `build_trading_presenter_state()`."""
    # BOT-033 — interval actually used by Load History/Start Live, set by
    # ChartToolbar.sig_timeframe_changed (see _ensure_chart_cards). An
    # instance attribute rather than the module constant so it can change
    # per-run without a restart.
    # EPIC-010H — Settings' DEFAULT_INTERVAL now reaches this screen too.
    # It used to read the module constant only, so editing Settings
    # changed the Backtest screen and silently left this one alone.
    config_values = presenter.config.get_all()
    presenter._active_interval = default_interval(config_values, FALLBACK_INTERVAL)

    # BOT-033 Phase 2 — symbol actually used by Load History/Start Live,
    # set from DashboardQmlViewModel.symbol at click time (see
    # StreamLifecycleController._on_load_history/_on_start_stream). An
    # instance attribute, same reasoning as _active_interval above: every
    # per-symbol chart-card lookup below (_rebuild_scripts,
    # _on_indicator_data, _on_script_region_data, _on_script_info_data,
    # _on_script_marker_data) must key off whatever symbol is actually
    # loaded, not the _DEFAULT_SYMBOLS[0] constant — otherwise switching
    # to a different symbol silently stops routing indicator data to the
    # (correctly re-keyed) chart card _ensure_chart_cards just built.
    presenter._active_symbol = default_symbol(config_values, FALLBACK_SYMBOL)

    # Custom indicator scripts (BOT-032) are the ONLY indicator mechanism
    # now (Phase 6 — no indicator is hardcoded in the engine; RSI/EMA/MACD
    # ship as default-registered scripts, see binance_bot_module.py).
    # Stored on self (not a local) — BOT-034's _compute_fetch_limit() also
    # needs it, to look up an enabled script's min_warmup_bars.
    presenter._script_registry = container.resolve(IndicatorScriptRegistry)
    # `BOT-063` — the Dev Board's per-script params dialog: a script's
    # declared `.inputs` turned into a form, and where an edited value
    # is saved. `get_script_params` below reads through this store on
    # every call (never cached), the same "no retroactive effect until
    # the next Load History/Start Live" contract enabling/disabling a
    # script already has.
    presenter._script_catalog = IndicatorScriptCatalog(presenter._script_registry)
    presenter._script_params_store = IndicatorScriptParamsStore(presenter.config)
    presenter._script_runner = IndicatorScriptRunner(
        registry=presenter._script_registry,
        emit_line=presenter.ui_indicator_data_signal.emit,
        emit_region=presenter.ui_script_region_signal.emit,
        emit_info=presenter.ui_script_info_signal.emit,
        emit_markers=presenter.ui_script_marker_signal.emit,
        on_error=presenter.ui_log_signal.emit,
        get_params=lambda key: presenter._script_params_store.load_all().get(key),
    )
    # ViewModel owns the enabled/disabled state (Phase 3) — the Presenter
    # only ever hands it what's available, once, same as logModel.
    presenter._view_model.script_model.set_available(
        presenter._script_registry.available()
    )

    # `EPIC-003G` — which chart card a script's data lands on, and how
    # many candles a fetch needs to warm every enabled script up.
    # `get_enabled_script_keys` is a lambda, not the bound method itself,
    # on purpose: `test_dashboard_presenter.py` monkeypatches
    # `presenter._enabled_script_keys` on the instance after
    # construction, and only a late `self._enabled_script_keys()` call
    # sees that — a captured bound method would keep calling the
    # original.
    presenter._indicator_coordinator = IndicatorCoordinator(
        script_registry=presenter._script_registry,
        script_runner=presenter._script_runner,
        config=presenter.config,
        get_active_charts=lambda: presenter.active_charts,
        get_active_symbol=lambda: presenter._active_symbol,
        get_enabled_script_keys=lambda: presenter._enabled_script_keys(),
        get_script_params=lambda key: presenter._script_params_store.load_all().get(
            key
        ),
    )
    presenter.view.set_indicator_script_dependencies(
        presenter._script_catalog, presenter._script_params_store
    )
