"""`BOT-144` — `DashboardPresenter`'s core construction: the view model, the
per-service DI resolves later sections depend on, the symbol-options
coordinator, FSM wiring, and the small per-run state dicts. Split out of
`presenter_factory.py` once that file itself crossed the 400-line ceiling
(`architecture-rule.md` §5.4) — see that file's own docstring for why this
whole construction sequence is a Builder over `presenter`, not an
independent-object Factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.symbol_options_coordinator import (
    SymbolOptionsCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_SYMBOL,
    default_symbol,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from sagittarius_engine.extensions.fsm import BaseStateMachine
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from ..dashboard_view_model import DashboardQmlViewModel

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from ..dashboard_presenter import DashboardPresenter
    from ..dashboard_view import DashboardView


def build_core_presenter_state(
    presenter: DashboardPresenter,
    view: DashboardView,
    container: IContainer,
    fsm: BaseStateMachine[Any],
) -> None:
    """View model, the DI resolves later sections read (`_thread_manager`
    onward), the symbol-options coordinator, FSM transitions/callbacks, and
    the cancellation token / per-run dicts. Call first, from
    `build_dashboard_presenter_state()` only — `fsm` is `presenter.fsm`,
    already narrowed non-None by the caller."""
    presenter._view_model = DashboardQmlViewModel()
    # EPIC-010H, middle tier: seed the form from Settings before the view
    # builds its widgets — `DevBoardPanel` reads `view_model.symbol` once
    # while constructing the combo. `restore_state()` later overrides this
    # with a remembered value if there is one, which is the top tier.
    # `DashboardQmlViewModel.symbol` is a PySide6 `@Property(str)`; mypy reads
    # the descriptor itself (`Property`) rather than the `str` it actually
    # holds at runtime — the same systemic false positive `pyproject.toml`'s
    # `[tool.mypy]` exclude list documents for `presentation/` (needs a
    # stub/plugin decision, not a per-line fix).
    presenter._view_model.symbol = default_symbol(  # type: ignore[assignment]
        presenter.config.get_all(), FALLBACK_SYMBOL
    )
    view.set_view_model(presenter._view_model)

    # Resolve IThreadManager exactly once — stored as an instance attribute.
    # No further container.resolve(IThreadManager) calls anywhere else.
    presenter._thread_manager = container.resolve(IThreadManager)
    # `EPIC-023D` — account-wide, shared with Trading (bấm ở Dev Board
    # hoặc Trading đều ra cùng một sự thật — xem EPIC-023's README §2).
    presenter._trading_session = container.resolve(ITradingSession)
    presenter._order_submission = container.resolve(IOrderSubmission)
    presenter._account = container.resolve(IAccountSnapshot)
    # `EPIC-023B` — the recorder outlives this screen (a DI singleton
    # written by `FuturesUserDataStream` regardless of whether Dev Board
    # is even open), same reasoning `TradingPresenter` documents for its
    # own `_equity_curve`.
    presenter._equity_curve = container.resolve(IEquityCurve)

    # EPIC-019A: shared with BackTestPresenter — `None` means "never
    # fetched", which is what makes the fetch happen once per session
    # rather than on every picker open. An empty list is a real answer
    # (the query returned nothing) and is deliberately NOT retried — a
    # distinction a falsy check would lose.
    presenter._symbol_options_coordinator = SymbolOptionsCoordinator(
        symbol_catalog=container.resolve(ISymbolCatalog),
        thread_manager=presenter._thread_manager,
        emit_ready=presenter._symbolOptionsReadySignal.emit,
        emit_failed=presenter._symbolOptionsFailedSignal.emit,
    )

    # Define allowed FSM transitions
    fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
    fsm.add_transition(UIMode.LOCKED, UIMode.LIVE)
    fsm.add_transition(UIMode.LOCKED, UIMode.ERROR)
    # BOT-123 — Stop (and the progress banner's Cancel) is now reachable
    # from LOCKED, not just LIVE: _on_stop_stream()'s unconditional
    # fsm.transition_to(UIMode.IDLE) needs this edge to actually succeed.
    # Without it, the very first Stop/Cancel click during a sync raised
    # InvalidStateTransitionError; the except-branch fallback to ERROR
    # happened to be valid from LOCKED and ERROR auto-recovers to IDLE
    # (_on_fsm_error below), so the screen didn't stay stuck — but every
    # cancel flashed a false "Error while stopping" log line and the WS
    # badge briefly read ERROR for nothing that actually failed. A
    # second cancel landing after that detour (already IDLE) had no such
    # detour and raised for real — see
    # test_stop_stream_is_a_no_op_once_already_idle.
    fsm.add_transition(UIMode.LOCKED, UIMode.IDLE)
    fsm.add_transition(UIMode.ERROR, UIMode.IDLE)
    fsm.add_transition(UIMode.LIVE, UIMode.IDLE)
    fsm.add_transition(UIMode.LIVE, UIMode.ERROR)

    # Automatically bind FSM state changes to UI Matrix
    presenter._bind_fsm_to_ui()

    # Top-bar WS status badge — a second, independent global callback
    # (BaseStateMachine supports multiple; see _bind_fsm_to_ui above).
    fsm.add_global_callback(presenter._on_fsm_state_changed_update_ws_badge)

    # Register Lifecycle Hooks for custom behaviors
    fsm.on_enter(UIMode.ERROR, presenter._on_fsm_error)

    presenter._apply_ws_status_badge(UIMode.IDLE)

    # BOT-034 — cooperative cancellation for background Load History/
    # Start Live work, checked at each step that would otherwise touch a
    # possibly-torn-down chart/view. "Individual tasks should still
    # implement cancellation tokens" is literally what
    # ThreadManagerExtension.shutdown()'s docstring asks for — it calls
    # thread_manager.shutdown(wait=False), so nothing else stops an
    # in-flight background method from continuing to run past app
    # shutdown. Reset on explicit Stop (see _on_stop_stream) so the next
    # Start Live isn't born pre-cancelled — mirrors how
    # BinanceWebsocketService makes a fresh CancellationToken per
    # start_stream() call rather than reusing one for its whole lifetime.
    presenter._cancellation_token = CancellationToken()
    presenter._shutdown_requested = False

    presenter.active_charts = {}

    # BOT-035 — full MarketData objects behind whatever's currently
    # rendered per symbol, kept in chronological order. ChartCard only
    # retains the (t, o, h, l, c) tuple projection it renders from
    # (_raw_history), which is not enough to correctly rebuild+refeed
    # IndicatorScriptRunner after a prepend (scripts need real MarketData,
    # and have no reset() — see history_pagination_controller.py's
    # docstring and BOT-035's task file §2.4). Overwritten (not appended)
    # on every Load History/Start Live, so a stale interval's klines
    # never leak into a later one.
    presenter._raw_klines_by_symbol = {}

    # `EPIC-021K` §2.3 — live-fill trade markers per symbol, keyed the
    # same way `_raw_klines_by_symbol` is (Dev Board is multi-symbol,
    # unlike Trading's single `_active_symbol`; every symbol with an
    # open chart card gets its own marker series drawn live).
    presenter._fill_markers_by_symbol = {}
