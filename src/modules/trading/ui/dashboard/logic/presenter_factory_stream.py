"""`BOT-144` — `DashboardPresenter`'s `StreamLifecycleController` wiring and
the construction's final steps (signal connections, the initial health
check, the equity chart seed, remembered-state restore, and the config-gated
autostart). Split out of `presenter_factory.py` once that file itself
crossed the 400-line ceiling (`architecture-rule.md` §5.4) — see that file's
own docstring for why this whole construction sequence is a Builder over
`presenter`, not an independent-object Factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_chart_adapter import (
    equity_samples_to_candles,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
    find_timeframe_pin_preferences,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.container_lookup import (
    find_state_coordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
    find_symbol_preferences,
)
from sagittarius_engine.extensions.fsm import BaseStateMachine
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from ..autostart_controller import AutoStartController
from ..stream_lifecycle_controller import StreamLifecycleController

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from ..dashboard_presenter import DashboardPresenter
    from ..dashboard_view import DashboardView

_AUTOSTART_ENABLED_CONFIG_KEY: str = "DEV_BOARD_AUTOSTART_ENABLED"
_DEFAULT_AUTOSTART_ENABLED: bool = False

#: How long AutoStartController waits for a real MarketTickEvent before
#: falling back to Load History (see autostart_controller.py). Configurable
#: so integration tests — which take real wall-clock time to run and offer
#: no real WS ticks ever — can push this window far out and get a
#: deterministic run instead of racing a fallback callback that fires mid
#: assertion. Production keeps the 2s default the design was built around.
_AUTOSTART_FALLBACK_SECONDS_CONFIG_KEY: str = "DEV_BOARD_AUTOSTART_FALLBACK_SECONDS"
_DEFAULT_AUTOSTART_FALLBACK_SECONDS: float = 2.0


def build_stream_presenter_state(
    presenter: DashboardPresenter,
    view: DashboardView,
    container: IContainer,
    fsm: BaseStateMachine[Any],
) -> None:
    """`StreamLifecycleController` (plus the closures it needs and the three
    `_run_*` aliases callers still read off `presenter` directly), then every
    remaining `__init__` step: signal connections, the initial health check,
    the equity chart seed, remembered-state restore, and the config-gated
    autostart. Call last, from `build_dashboard_presenter_state()` only,
    after `build_indicator_presenter_state()` — `fsm` is `presenter.fsm`,
    already narrowed non-None by the caller."""

    def _get_cancellation_token():
        return presenter._cancellation_token

    def _reset_cancellation_token():
        presenter._cancellation_token = CancellationToken()
        return presenter._cancellation_token

    def _get_active_interval():
        return presenter._active_interval

    def _set_active_interval(val: str):
        presenter._active_interval = val

    def _set_active_symbol(val: str):
        presenter._active_symbol = val

    presenter._stream_controller = StreamLifecycleController(
        thread_manager=presenter._thread_manager,
        market_data_sync=container.resolve(IMarketDataSync),
        historical_klines=container.resolve(IHistoricalKlines),
        market_stream=container.resolve(IMarketStream),
        config=presenter.config,
        fsm=fsm,
        view_model=presenter._view_model,
        script_runner=presenter._script_runner,
        raw_klines_by_symbol=presenter._raw_klines_by_symbol,
        get_active_interval=_get_active_interval,
        set_active_interval=_set_active_interval,
        set_active_symbol=_set_active_symbol,
        ensure_chart_cards=lambda symbols: presenter._ensure_chart_cards(symbols),
        rebuild_scripts=lambda: presenter._rebuild_scripts(),
        compute_fetch_limit=lambda: presenter._compute_fetch_limit(),
        get_cancellation_token=_get_cancellation_token,
        reset_cancellation_token=_reset_cancellation_token,
        emit_history_reloaded=presenter.ui_history_reloaded_signal.emit,
        emit_history_load_finished=presenter.ui_history_load_finished_signal.emit,
        emit_history_prepended=presenter.ui_history_prepended_signal.emit,
        emit_history_prepend_finished=presenter.ui_history_prepend_finished_signal.emit,
        emit_stream_success=presenter.ui_stream_success_signal.emit,
        emit_stream_failed=presenter.ui_stream_failed_signal.emit,
        emit_log=presenter.ui_log_signal.emit,
        emit_sync_progress=presenter.ui_sync_progress_signal.emit,
    )

    presenter._run_load_history = presenter._stream_controller._run_load_history
    presenter._run_load_more_history = (
        presenter._stream_controller._run_load_more_history
    )
    presenter._run_sync_and_start = presenter._stream_controller._run_sync_and_start

    # Must be called explicitly at the end of BasePresenter's contract.
    presenter._connect_ui_signals()
    presenter._connect_engine_events()
    presenter._trigger_initial_health_check()

    # `EPIC-023B` — read *after* `_connect_engine_events()` has already
    # subscribed `_equity_feed`, not before: a live sample recorded in
    # between subscribing and reading is otherwise missed entirely
    # (subscribed-after-read order), same reasoning `TradingPresenter`
    # documents for its own identical seed call.
    presenter.view.equity_chart.render_historical_data(
        equity_samples_to_candles(presenter._equity_curve.samples())
    )

    # EPIC-010D — restore the remembered form values, then start tracking
    # changes. Placed here deliberately: after `_active_interval` and the
    # ViewModel exist for `restore_state()` to write into, and *before*
    # the auto-start block below, which (when config-enabled) calls
    # `_on_start_stream()` immediately and would otherwise stream the
    # default symbol rather than the remembered one.
    #
    # Restoring first and only then connecting `_mark_dirty` keeps the
    # restore from writing the values straight back out as if the user
    # had just typed them.
    presenter._state_coordinator = find_state_coordinator(container)
    if presenter._state_coordinator is not None:
        presenter._state_coordinator.restore_into(presenter)
    # EPIC-014 — the shared symbol favourites/recents store, injected
    # into the panel that owns the picker. Optional exactly like the
    # coordinator above: a presenter built against a container that does
    # not know about it keeps an unpersisted store and still works.
    view.set_symbol_preferences(
        find_symbol_preferences(container) or SymbolPreferences()
    )
    # Follow-up to `EPIC-015` Phase 4 — the shared, per-symbol pinned-
    # timeframe store. Optional exactly like the coordinator/symbol
    # store above: set before `_ensure_chart_cards()` is ever invoked
    # (it runs later, off the first market tick/health check, via the
    # `ensure_chart_cards` lambda handed to `StreamLifecycleController`
    # above), so every ChartCard Dev Board builds — now or on a later
    # symbol-list rebuild — is scoped against the same store.
    view.set_timeframe_pin_preferences(
        find_timeframe_pin_preferences(container) or TimeframePinPreferences()
    )

    presenter._view_model.script_model.enabledKeysChanged.connect(
        presenter._mark_state_dirty
    )
    presenter._view_model.symbolChanged.connect(presenter._mark_state_dirty)
    presenter._view_model.startDateChanged.connect(presenter._mark_state_dirty)
    presenter._view_model.endDateChanged.connect(presenter._mark_state_dirty)

    # EPIC-006D: DevBoardPanel.qml is no longer loaded here — view's
    # set_view_model() now builds the QtWidgets DevBoardPanel directly.
    # .qml file kept on disk, unloaded (EPIC-006's rollback convention).

    # BOT-034 — auto-start Start Live the moment the Dev Board opens,
    # falling back to Load History if no MarketTickEvent proves a real
    # connection within a few seconds. Constructed last: it immediately
    # calls _on_start_stream(), which needs everything above already set
    # up (script runner, signal connections, FSM). Config-gated
    # (default off — BOT-062: opening Dev Board must not silently start
    # a live connection unless the user has opted in); `None` when
    # disabled so `_on_ui_chart_update`'s `self._autostart.on_market_tick()`
    # has to guard against that instead of assuming it always exists.
    presenter._autostart = None
    is_autostart_enabled = presenter.config.get(
        _AUTOSTART_ENABLED_CONFIG_KEY,
        _DEFAULT_AUTOSTART_ENABLED,
        cast=bool,
    )
    if is_autostart_enabled:
        fallback_seconds = presenter.config.get(
            _AUTOSTART_FALLBACK_SECONDS_CONFIG_KEY,
            _DEFAULT_AUTOSTART_FALLBACK_SECONDS,
            cast=float,
        )
        presenter._autostart = AutoStartController(
            start_stream=presenter._on_start_stream,
            load_history=presenter._on_load_history,
            fallback_seconds=fallback_seconds,
            parent=presenter,
        )
        presenter._autostart.begin()
