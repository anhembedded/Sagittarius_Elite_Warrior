"""`EPIC-029F` — the Bots screen's presenter.

Reads the bots through the bots queries, never the store (`BotChangedEvent`
says when to read again, coalesced so a burst of fills is one read); judges
the selected bot's parameters through its kind on every edit; and sends one
command at a time through `BotActionsCoordinator`, locking the screen while
it runs (`async-ui-action-rule.md`). A late answer to an action or a read
that is no longer current is dropped and logged, never shown.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_actions_coordinator import (
    BotActionsCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_changes_feed import (
    BotChangesFeed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_chart_host import (
    BotChartHost,
    BotChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_commands import (
    PendingAction,
    command_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_log_feed import (
    BotLogFeed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
    dialogs_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_ui_fsm_matrix import (
    BOTS_UI_TRANSITIONS,
    BotsUiEvent,
    BotsUiState,
    selection_event,
    settled_event,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    BotQueries,
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.extensions.fsm.declarative_state_machine import (
    DeclarativeStateMachine,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .bots_view import BotsView

logger = logging.getLogger("App.Bots.Screen")

_ACTION = "bot_action"
#: A burst of store writes (a fill books, then the level moves) is one read.
_COALESCE_MS = 150
#: Edits are judged once typing pauses.
_REJUDGE_MS = 150
#: The running time ticks in minutes.
_CLOCK_MS = 30_000


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BotsPresenter(BasePresenter):
    """@brief Orchestrates the Bots screen."""

    # The engine declares both as plain `None` defaults, untyped, so any real
    # value is an "incompatible override" to mypy; the FSM reads them as-is.
    INITIAL_STATE = BotsUiState.NO_SELECTION  # type: ignore[assignment]
    UI_TRANSITION_MATRIX = BOTS_UI_TRANSITIONS  # type: ignore[assignment]

    def __init__(
        self,
        view: BotsView,
        container: IContainer,
        *,
        dialogs: BotsDialogs | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        super().__init__(view, container)
        threads = container.resolve(IThreadManager)
        self._model = view.model
        self._dialogs = dialogs or dialogs_for(view)
        self._now = now
        self._catalog = container.resolve(IBotKindCatalog)
        self._venues = container.resolve(IVenueTradingPorts)
        self._ticks = BotTickFeed(self.event_bus, MarketType.SPOT, parent=self)
        feed = MarketDataCandleFeed(
            container.resolve(IMarketDataSync),
            container.resolve(IHistoricalKlines),
            container.resolve(IMarketStream),
            MarketType.SPOT,
        )
        self._charts = BotChartHost(BotChartPorts(threads, feed, self._ticks))
        self._reads = FencedReads(
            threads, {kind: ActionOwnershipTracker() for kind in ReadKind}
        )
        self._actions: ActionOwnershipTracker[str, PendingAction, BotsUiState] = (
            ActionOwnershipTracker()
        )
        commands = container.resolve(ICommandDispatcher)
        self._queries = BotQueries(commands, self._reads)
        self._commands = BotActionsCoordinator(commands, threads)
        self._changes = BotChangesFeed(self.event_bus, parent=self)
        self._log = BotLogFeed(parent=self)
        self._selected = SelectedBot(self._catalog, now)
        self._select_after_create = ""
        self._reread = _single_shot(self, _COALESCE_MS, self._queries.bots)
        self._rejudge = _single_shot(self, _REJUDGE_MS, self._refresh_detail)
        self._clock = QTimer(self)
        self._clock.setInterval(_CLOCK_MS)
        self._connect()
        self._clock.start()
        self._queries.bots()

    # -- wiring ------------------------------------------------------------ #

    def _connect(self) -> None:
        model = self._model
        model.select_requested.connect(self._on_select)
        model.new_bot_requested.connect(self._on_new_bot)
        model.action_requested.connect(self._on_action)
        model.refresh_fills_requested.connect(
            lambda: self._queries.fills(self._model.selected)
        )
        self.view.detail.fit_levels_requested.connect(self._charts.fit_levels)
        self._reads.answered.connect(self._on_read_answered)
        self._reads.failed.connect(self._on_failed)
        self._commands.finished.connect(self._on_finished)
        self._changes.changed.connect(lambda *_: self._reread.start())
        self._log.line.connect(model.append_log_line)
        self._ticks.candle.connect(self._on_candle)
        self._clock.timeout.connect(self._refresh_detail)

    # -- reads ------------------------------------------------------------- #

    def _on_read_answered(self, kind: ReadKind, label: str, answer: object) -> None:
        selected = self._model.selected
        if kind is ReadKind.LIST and isinstance(answer, BotList):
            self._on_list(answer)
        elif selected is None or label != selected.bot_id:
            logger.debug(
                "Bots screen: %s for %s arrived after the selection moved",
                kind.value,
                label,
            )
        elif kind is ReadKind.PLANNER and isinstance(answer, PlannerMarket):
            self._selected.take_market(answer)
            self._refresh_detail()
        elif kind is ReadKind.FILLS and isinstance(answer, BotFills):
            self._model.set_fills(answer)

    def _on_failed(self, kind: ReadKind, label: str, error: str) -> None:
        if kind is ReadKind.FILLS:
            self._model.set_fills(BotFills(problem=error))
            return
        self._model.set_status(f"Could not read the {kind.value}: {error}", True)

    def _on_list(self, bots: BotList) -> None:
        self._model.set_bots(bots.bots)
        if bots.refused:
            names = ", ".join(refused.name for refused in bots.refused)
            self._model.set_status(f"Bot files that could not be read: {names}", True)
        wanted = self._select_after_create or (
            self._model.selected.bot_id if self._model.selected else ""
        )
        fresh = next((bot for bot in bots.bots if bot.bot_id == wanted), None)
        if self._busy():
            self._model.set_selected(fresh)
            if fresh is not None:
                self._selected.take_snapshot(fresh)
        elif fresh is not None and self._select_after_create:
            self._select_after_create = ""
            self._select(fresh)
        elif fresh is None or self._model.selected is None:
            if self._model.selected is not None:
                self._select(None)
        else:
            self._model.set_selected(fresh)
            self._selected.take_snapshot(fresh)
            self._dispatch(selection_event(fresh))
            self.view.set_chart(self._charts.show(fresh))
        self._refresh_detail()

    # -- selection and detail ---------------------------------------------- #

    def _on_select(self, bot_id: str) -> None:
        if self._busy():
            return
        current = self._model.selected
        if current is not None and current.bot_id == bot_id:
            return
        self._select(
            next((bot for bot in self._model.bots if bot.bot_id == bot_id), None)
        )

    def _select(self, bot: BotSnapshot | None) -> None:
        self._model.set_selected(bot)
        self._dispatch(selection_event(bot))
        self.view.set_chart(self._charts.show(bot))
        panel = self._selected.select(bot)
        if panel is not None:
            panel.config_changed.connect(self._on_config_edited)
        self.view.set_kind_panel(panel)
        self._refresh_detail()
        if bot is not None:
            self._queries.planner(bot)
            self._queries.fills(bot)

    def _refresh_detail(self) -> None:
        detail = self._selected.detail()
        self._model.set_facts(detail.facts if detail else None)
        self._model.set_judgement(
            detail.verdict_lines if detail else (), detail.refusal if detail else ""
        )
        self._model.set_availability(detail.availability if detail else {})
        self._charts.draw(detail.overlay if detail else None)

    def _on_config_edited(self, config: Mapping[str, str]) -> None:
        self._selected.edit(config)
        self._rejudge.start()

    def _on_candle(self, candle: MarketData) -> None:
        if self._selected.take_price(candle.symbol, Decimal(str(candle.close_price))):
            detail = self._selected.detail()
            self._model.set_facts(detail.facts if detail else None)

    # -- actions ----------------------------------------------------------- #

    def _on_action(self, value: str) -> None:
        bot = self._model.selected
        if bot is None or self._busy():
            return
        command = command_for(
            BotAction(value), bot, self._dialogs, self._selected.edited
        )
        if command is not None:
            self._begin(PendingAction(f"{value} {bot.name}", BotAction(value)), command)

    def _on_new_bot(self) -> None:
        if self._busy():
            return
        kinds = [kind.kind_id for kind in self._catalog.kinds()]
        venues = [v for v in self._venues.enabled() if v.market_type is MarketType.SPOT]
        command = self._dialogs.ask_new_bot(kinds, venues)
        if command is not None:
            self._begin(PendingAction(f"Create {command.name}"), command)

    def _begin(self, pending: PendingAction, command: object) -> None:
        previous = (
            self.fsm.current_state if self.fsm is not None else BotsUiState.NO_SELECTION
        )
        label = pending.label
        action = self._actions.begin_action(_ACTION, pending, previous)
        self._dispatch(BotsUiEvent.ACTION_STARTED)
        self._model.set_status(f"{label}…", False)
        logger.info("Bots screen: %s", label)
        self._commands.send(action.action_id, command)

    def _on_finished(self, action_id: int, result: object, error: str) -> None:
        if not self._actions.is_current_pending(action_id, _ACTION):
            self._actions.log_stale_callback("_on_finished", action_id, _ACTION)
            return
        active = self._actions.active_action
        pending = active.config if active else PendingAction("")
        label = pending.label
        accepted = isinstance(result, BotCommandResult) and result.accepted
        self._actions.finish_action(
            action_id, ActionOutcome.SUCCEEDED if accepted else ActionOutcome.FAILED
        )
        if accepted and isinstance(result, BotCommandResult):
            self._model.set_status(f"{label}: done.", False)
            if pending.action is None and result.bot_id:
                self._select_after_create = result.bot_id
            if pending.action is BotAction.SAVE:
                self._selected.saved()
        else:
            reason = result.message if isinstance(result, BotCommandResult) else error
            self._model.set_status(f"{label}: refused. {reason}", True)
        logger.info("Bots screen: %s %s", label, "accepted" if accepted else "refused")
        self._dispatch(settled_event(self._model.selected))
        self._follow_selection()
        self._queries.bots()

    def _follow_selection(self) -> None:
        """A list read that landed during the action may have moved the
        selection (the bot gone); the detail follows it here, once the screen
        may select again, so no bot's facts outlive it."""
        shown = self._selected.bot
        wanted = self._model.selected
        if (shown.bot_id if shown else None) != (wanted.bot_id if wanted else None):
            self._select(wanted)
        else:
            self._refresh_detail()

    # -- helpers ----------------------------------------------------------- #

    def _busy(self) -> bool:
        return (
            self.fsm is not None
            and self.fsm.current_state is BotsUiState.ACTION_IN_FLIGHT
        )

    def _dispatch(self, event: BotsUiEvent) -> None:
        fsm = self.fsm
        if isinstance(fsm, DeclarativeStateMachine) and fsm.can_dispatch(event):
            fsm.dispatch(event)

    def shutdown(self) -> None:
        """Answers in flight are dropped; the chart's stream and the log
        handler are released; nothing is cancelled at the exchange."""
        self._actions.invalidate_active()
        self._reads.drop_all()
        for timer in (self._reread, self._rejudge, self._clock):
            timer.stop()
        self._charts.close()
        self._log.close()
        self._changes.stop()
        self._ticks.stop()


def _single_shot(
    parent: BotsPresenter, interval: int, slot: Callable[[], None]
) -> QTimer:
    timer = QTimer(parent)
    timer.setSingleShot(True)
    timer.setInterval(interval)
    timer.timeout.connect(slot)
    return timer
