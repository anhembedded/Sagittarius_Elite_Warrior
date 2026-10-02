"""`BOT-144` — `DashboardPresenter`'s trading-card construction: the live
order book, the strategy-arming coordinator, the Enable/Disable and
Emergency Stop controls (`DeskSessionControls`, `EPIC-028M`) and the
manual-order/cancel `TradingActionsCoordinator`. Split out of
`presenter_factory.py` once that file itself crossed the 400-line ceiling
(`architecture-rule.md` §5.4) — see that file's own docstring for why this
whole construction sequence is a Builder over `presenter`, not an
independent-object Factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    SUPPORTED_LIVE_INTERVALS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_armed_strategy_reader import (
    IArmedStrategyReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_session_controls import (
    DeskSessionControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.live_order_book_coordinator import (
    LiveOrderBookCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_arming_coordinator import (
    StrategyArmingCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)

from ..coordinators.trading_actions_coordinator import (
    CompletionEmitters,
    TradingActionsCoordinator,
)
from ..history_pagination_controller import HistoryPaginationController

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from ..dashboard_presenter import DashboardPresenter

#: `EPIC-023C` — same action-kind string `TradingPresenter` uses for its own
#: `ActionOwnershipTracker`; the two trackers are separate instances (each
#: Presenter owns its own, `async-ui-action-rule.md` §2), so identical
#: strings here do not collide.
_ARM_ACTION = "arm_strategy"

#: `EPIC-024B` — manual trading card. One tracker for the whole card (like
#: a toggle): the form represents exactly one pending attempt
#: at a time, never two concurrent Long/Short clicks from the same card.
_MANUAL_ORDER_ACTION = "manual_order"


def build_trading_presenter_state(
    presenter: DashboardPresenter, container: IContainer
) -> None:
    """The order book, strategy-arming coordinator, and the toggle/emergency-
    stop/manual-order `TradingActionsCoordinator` (plus the pagination
    controller, which has no better home). Call second, from
    `build_dashboard_presenter_state()` only, after
    `build_core_presenter_state()`."""
    # `EPIC-023A` — Vị thế/Lệnh chờ khớp, account-wide state read via
    # `OrderFeed`. Empty until the next successful `ITradingSession.enable()`
    # reconciles them (bấm ở Dev Board hoặc Trading đều được — cả hai
    # đi qua cùng một `ITradingSession` singleton) — same starting shape
    # `TradingPresenter`'s own `LiveOrderBookCoordinator` has, not a gap
    # introduced here.
    presenter._order_book = LiveOrderBookCoordinator(
        view=presenter.view, emit_log=presenter._append_log
    )

    # `EPIC-023C` — the strategy card. Constructed before
    # `_connect_ui_signals()` so its signals have something to reach,
    # same reasoning `TradingPresenter` documents for its own identical
    # construction. `_active_symbol` is not read until the user actually
    # arms (the lambda below), well after it is assigned further down
    # this constructor.
    presenter._armed_strategy = container.resolve(IArmedStrategyReader)
    presenter._arm_tracker = ActionOwnershipTracker()
    presenter._arming_coordinator = StrategyArmingCoordinator(
        # PR 2.1e gave the card one shared owner; PR 4.3m keeps it that
        # way, just relocated out of `modules/strategy/ui/` — the
        # card's own view model, not the screen's. `.strategy` is a
        # PySide6 `@Property`; same documented mypy false positive as the
        # `.symbol` assignment in `presenter_factory_core.py`.
        view_model=presenter._view_model.strategy,  # type: ignore[arg-type]
        catalog=container.resolve(IStrategyCatalogReader),
        arming=container.resolve(IStrategyArmingControl),
        get_active_symbol=lambda: presenter._active_symbol,
        get_armed_config=lambda: presenter._armed_strategy.armed().config,
        tracker=presenter._arm_tracker,
        arm_action_kind=_ARM_ACTION,
        set_status=lambda message, _is_error: presenter._append_log(message),
        append_log=presenter._append_log,
        on_armed_changed=presenter._on_armed_config_changed,
    )
    presenter._arming_coordinator.restore_into_view_model(
        list(SUPPORTED_LIVE_INTERVALS)
    )
    presenter._refresh_armed_summary(busy=False)

    # `EPIC-023D` — Enable/Disable trading + Emergency Stop for the venue
    # this board shows, through the desks' own controls (`EPIC-028M`). Each
    # instance holds its own two trackers (`BUG-089`), never shared with
    # `_arm_tracker` or a desk's (`async-ui-action-rule.md` §2).
    presenter._session_controls = DeskSessionControls(
        presenter._trading_session,
        presenter._thread_manager,
        container.resolve(TradingVenue),
        presenter,
    )
    # `EPIC-024B` — manual trading card. Own tracker (a manual order attempt
    # must not fence, or be fenced by, an unrelated toggle/stop/arm click).
    presenter._manual_order_tracker = ActionOwnershipTracker()
    # `EPIC-024B` — last live close price per symbol, the manual order
    # card's `reference_price` for a MARKET order (a LIMIT order's own
    # price field is the reference instead — see `_on_manual_order_requested`).
    # Updated on every `_on_ui_chart_update` tick; `Decimal`, not the
    # `float` the tick itself carries — `OrderRequest` requires it.
    presenter._last_price_by_symbol = {}
    # `BOT-144` — trackers stay Presenter-owned (`async-ui-action-rule.md` §2).
    presenter._trading_actions = TradingActionsCoordinator(
        thread_manager=presenter._thread_manager,
        order_submission=presenter._order_submission,
        account=presenter._account,
        # `EPIC-027K` post-review fix (PR #284) — `manual_order_intent_for()`
        # refuses a Short click on a market with no short capability; the
        # venue is resolved once here, like every other venue-branched bind
        # in `adapter_bindings.py`, not re-read per click.
        market_type=container.resolve(TradingVenue).market_type,
        manual_order_tracker=presenter._manual_order_tracker,
        manual_order_action_kind=_MANUAL_ORDER_ACTION,
        completion_emitters=CompletionEmitters(
            manual_order=presenter.manualOrderCompleted.emit,
            cancel_order=presenter.cancelOrderCompleted.emit,
        ),
        set_manual_order_state=presenter._view_model.set_manual_order_state,
        append_log=presenter._append_log,
        get_active_symbol=lambda: presenter._active_symbol,
        get_last_price=lambda symbol: presenter._last_price_by_symbol.get(symbol),
    )
    # Seeds from whatever the session already says — if Trading enabled it
    # first, opening Dev Board must show "đang BẬT", never a default "TẮT"
    # that contradicts the account's real state.
    presenter._view_model.set_trading_state(
        presenter._trading_session.snapshot().enabled, False
    )
    presenter._refresh_session_stats()

    # BOT-035 — one collaborator per Dev Board screen, same lifetime
    # pattern as AutoStartController: constructed once here, torn down
    # implicitly with the presenter (parented to self).
    presenter._pagination = HistoryPaginationController(
        fetch_older=presenter._fetch_older_history,
        recheck_edge=presenter._recheck_edge,
        parent=presenter,
    )
