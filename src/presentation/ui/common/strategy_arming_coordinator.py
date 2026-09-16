"""`EPIC-022D`/`EPIC-022F` — a screen's strategy card, minus the widgets.

@details Holds the parameter values the user is editing, turns the card's
two buttons into `ArmStrategyCommand`/`DisarmStrategyCommand`, and
persists a successful arming to `IConfig` so the next session starts from
the same choice.

Split out of `TradingPresenter` rather than added to it: that file was
already 729 lines before this feature, and `async-ui-action-rule.md` §2
says a Presenter whose background-action logic outgrows one file splits
by feature slice. Per that same section this Coordinator owns **no**
action-id/cancellation bookkeeping — the owning Presenter keeps its own
`ActionOwnershipTracker` and calls in here; nothing below starts its own
background work.

`EPIC-023C` moved this out of `screens/trading/coordinators/` into
`common/` once Dev Board needed the identical strategy card — every
dependency already arrived through the `view_model`/`dispatcher`/callable
Protocol below, with zero direct reference to `TradingPresenter`/
`TradingViewModel`, so the move is a pure path change. Importing across
from `screens/dashboard/` into a sibling screen's private `coordinators/`
dir would have been the cross-screen-import anti-pattern
`architecture-rule.md` §5 documents — the same reason `EPIC-023A`/`B`
already promoted `PositionsPanel`/`OpenOrdersPanel`/`equity_chart_adapter.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.arm_strategy import (
    ArmStrategyBlockReason,
    ArmStrategyCommand,
    ArmStrategyCommandHandler,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disarm_strategy import (
    DisarmStrategyCommand,
    DisarmStrategyCommandHandler,
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.presentation.enum_labels import EnumLabels
from Sagittarius_Elite_Warrior.src.presentation.ui.common.strategy_display import (
    humanize_strategy_key,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.strategy_params import (
    build_bot_params_rows,
    build_bot_params_schema,
    parse_bot_params,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)

logger = logging.getLogger("App.TradingStrategyArming")

#: English copy for each refusal. Every branch of
#: `ArmStrategyBlockReason` has a line here — a missing one would surface
#: as a silent no-op button, which is the failure mode this whole epic
#: exists to remove.
ARM_BLOCK_MESSAGES = EnumLabels(
    ArmStrategyBlockReason,
    {
        ArmStrategyBlockReason.TRADING_IS_ENABLED: (
            "Trading is active — turn off trading before changing strategy."
        ),
        ArmStrategyBlockReason.STRATEGY_NOT_FOUND: (
            "This strategy was not found in the registered list."
        ),
        ArmStrategyBlockReason.INVALID_PARAMS: "Strategy Parameters are invalid.",
        ArmStrategyBlockReason.MISSING_SYMBOL_OR_INTERVAL: (
            "Both symbol and trading timeframe must be selected."
        ),
    },
)
DISARM_BLOCKED_MESSAGE = (
    "Trading is active — turn off trading before removing the strategy."
)


class CommandDispatcher(Protocol):
    """The one method this Coordinator needs from the dispatcher.

    @details `architecture-rule.md` requires explicit contracts rather
    than implicit duck-typing. This used to be an untyped `dispatcher`
    parameter, which said nothing about what was expected and let a test
    pass anything at all (`BOT-125` review).
    """

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> Any: ...


class StrategyCardViewModel(Protocol):
    """What the strategy card's Coordinator reads from and writes to.

    @details Narrower than `TradingViewModel` on purpose: this Coordinator
    has no business touching the toggle, the chart, or the session stats
    that ViewModel also carries, and naming only what it uses is what makes
    that reviewable.
    """

    @property
    def selectedStrategyKey(self) -> str: ...

    @property
    def liveInterval(self) -> str: ...

    @property
    def sizingPercent(self) -> float: ...

    @property
    def leverage(self) -> float: ...

    def set_strategy_options(
        self, strategy_options: list[dict], interval_options: list[str]
    ) -> None: ...

    def set_strategy_selection(
        self, strategy_key: str, interval: str, sizing_percent: float, leverage: float
    ) -> None: ...

    def set_bot_params(self, schema: list[dict], rows: list[dict]) -> None: ...

    def set_bot_params_error(self, message: str) -> None: ...


class StrategyArmingCoordinator:
    """@brief Strategy selection, parameters, arming and persistence for
    the Trading screen."""

    def __init__(
        self,
        view_model: StrategyCardViewModel,
        config,
        dispatcher: CommandDispatcher,
        available_strategies: Callable[[], Mapping[str, type]],
        get_active_symbol: Callable[[], str],
        get_armed_config: Callable[[], LiveStrategyConfig | None],
        tracker: ActionOwnershipTracker,
        arm_action_kind: str,
        set_status: Callable[[str, bool], None],
        append_log: Callable[[str], None],
        on_armed_changed: Callable[[LiveStrategyConfig | None, bool], None],
    ) -> None:
        self._view_model = view_model
        self._dispatcher = dispatcher
        self._available_strategies = available_strategies
        self._get_active_symbol = get_active_symbol
        self._get_armed_config = get_armed_config
        #: Owned by `TradingPresenter`, handed in — never minted here
        #: (`async-ui-action-rule.md` §2).
        self._tracker = tracker
        self._arm_action_kind = arm_action_kind
        self._set_status = set_status
        self._append_log = append_log
        self._on_armed_changed = on_armed_changed
        self._store = LiveStrategyConfigStore(config)
        self._params: dict[str, Any] = {}
        #: Sentinel for "the form has never been built", distinct from
        #: `""` which legitimately means "no strategy is picked".
        self._last_form_strategy_key = "\x00never-built"

    # ------------------------------------------------------------------ #
    # Restore (`EPIC-022F`)
    # ------------------------------------------------------------------ #

    def restore_into_view_model(self, interval_options: list[str]) -> None:
        """Fills the card from `trading.live_*` — and does nothing else.

        @details No `ArmStrategyCommand`, no `EnableTradingCommand`, no
        network call. `BUG-101` (a Backtest restore that fired a real
        200k-row query because it went through the same setters a user
        does) and `BUG-104` (a remembered route that started a live
        stream on boot) are the same bug twice; this method is written to
        not be its third occurrence. After a restore the screen shows the
        saved choice and nothing is armed, so the user still has to press
        "Nạp chiến lược" themselves.
        """
        available = sorted(self._available_strategies())
        self._view_model.set_strategy_options(
            [{"key": key, "label": humanize_strategy_key(key)} for key in available],
            interval_options,
        )
        try:
            saved = self._store.load()
        except ValueError as exc:
            # A saved config the domain rejects (leverage 0, an interval
            # live trading does not support) must not blank the card or
            # crash the screen — show the defaults and say why.
            logger.warning("Saved strategy configuration is invalid: %s", exc)
            saved = LiveStrategyConfig(strategy_key="", symbol="", interval="")
            self._view_model.set_bot_params_error(str(exc))

        saved_key = saved.strategy_key
        if saved_key not in available:
            # A saved key that no longer exists (renamed, removed) must
            # not be shown as if it were selectable. The combo falls back
            # to the first real strategy so the card is never empty — but
            # nothing is armed either way, so the fallback can only ever
            # become live if the user presses "Nạp chiến lược" on it.
            saved_key = available[0] if available else ""
        self._params = dict(saved.strategy_params)
        self._view_model.set_strategy_selection(
            saved_key, saved.interval, saved.sizing_percent, saved.leverage
        )
        self.refresh_params_rows()

    # ------------------------------------------------------------------ #
    # "Thông số Chiến lược"
    # ------------------------------------------------------------------ #

    def refresh_params_rows(self) -> None:
        """Rebuilds the parameter form for whatever strategy is selected."""
        strategy_cls = self._selected_strategy_class()
        if strategy_cls is None:
            self._view_model.set_bot_params([], [])
            return
        schema = build_bot_params_schema(strategy_cls, self._params)
        self._view_model.set_bot_params(schema, build_bot_params_rows(schema))
        self._view_model.set_bot_params_error("")

    def apply_params(self, raw_values: Mapping[str, Any]) -> bool:
        """@returns Whether the values were accepted.

        @details Validation is `parse_bot_params` against the strategy's
        own declared `inputs` — the same call the Backtest screen makes,
        so a value accepted on one screen cannot be rejected on the other.
        """
        strategy_cls = self._selected_strategy_class()
        if strategy_cls is None:
            return False
        try:
            parsed = parse_bot_params(strategy_cls().inputs, raw_values)
        except ValueError as exc:
            self._view_model.set_bot_params_error(str(exc))
            return False
        self._params = dict(parsed)
        self._view_model.set_bot_params_error("")
        self.refresh_params_rows()
        return True

    def _selected_strategy_class(self) -> type | None:
        return self._available_strategies().get(self._view_model.selectedStrategyKey)

    # ------------------------------------------------------------------ #
    # Arm / disarm
    # ------------------------------------------------------------------ #

    def build_config(self) -> LiveStrategyConfig:
        return LiveStrategyConfig(
            strategy_key=self._view_model.selectedStrategyKey,
            symbol=self._get_active_symbol(),
            interval=self._view_model.liveInterval,
            strategy_params=dict(self._params),
            sizing_percent=self._view_model.sizingPercent,
            leverage=self._view_model.leverage,
        )

    def on_arm_clicked(self) -> None:
        """The "Nạp chiến lược" button, end to end.

        @details Moved here from `TradingPresenter` (`BOT-125` review):
        the Presenter had grown to 926 lines, well past the 400 that
        `architecture-rule.md` §5 makes a hard split threshold, and this
        block is one coherent feature slice — the same reason
        `async-ui-action-rule.md` §2 gives for Coordinators existing.

        Action ownership stays the Presenter's: it owns the tracker and
        hands it in, which §2 explicitly sanctions ("a single shared
        tracker the Presenter owns and hands to every Coordinator") and
        distinguishes from a Coordinator minting its own action ids.
        """
        action = self._tracker.begin_action(self._arm_action_kind, None, None)
        self._report_state(busy=True)
        try:
            result = self.arm()
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
            self._report_state(busy=False)
            self._set_status(f"Error arming strategy: {exc}", True)
            return

        self._tracker.finish_action(
            action.action_id,
            ActionOutcome.SUCCEEDED if result.armed else ActionOutcome.FAILED,
        )
        self._report_state(busy=False)
        if result.armed:
            summary = self.armed_summary(self._get_armed_config())
            self._set_status(f"Strategy armed: {summary}", False)
            self._append_log(f"Strategy armed: {summary}")
            return

        # A total mapping — `result.block_reason` is non-None on this
        # branch, and every member has a line by construction.
        message = ARM_BLOCK_MESSAGES[result.block_reason]
        if result.error_message:
            message = f"{message} ({result.error_message})"
        self._set_status(message, True)

    def on_disarm_clicked(self) -> None:
        """The "Gỡ" button, end to end."""
        try:
            result = self.disarm()
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            self._set_status(f"Error removing strategy: {exc}", True)
            return
        self._report_state(busy=False)
        if result.disarmed:
            self._set_status("Strategy removed.", False)
        else:
            self._set_status(DISARM_BLOCKED_MESSAGE, True)

    def on_strategy_selection_changed(self) -> None:
        """Rebuilds the parameter form when the PICKED strategy changes.

        @details Picking is not arming: nothing here dispatches a command,
        rebuilds an engine or touches the exchange. `BUG-101` was exactly
        this distinction being lost on the Backtest screen, where a value
        arriving through a setter ran real work.

        `strategyConfigChanged` also fires for sizing/leverage/interval
        edits, so the key is compared first — rebuilding the whole form on
        each of those would discard values the user is mid-way through
        typing.
        """
        key = self._view_model.selectedStrategyKey
        if key == self._last_form_strategy_key:
            return
        self._last_form_strategy_key = key
        self.refresh_params_rows()

    def _report_state(self, *, busy: bool) -> None:
        """Pushes what the SESSION says is armed, never what the combo
        shows — the two differ on purpose between picking and arming."""
        self._on_armed_changed(self._get_armed_config(), busy)

    def arm(self) -> ArmStrategyResult:
        """Runs `ArmStrategyCommand`; persists only on success.

        @details Persisting only a successful arming is deliberate: a
        half-typed parameter set that the strategy rejected is not a
        configuration worth reloading next session, and writing it would
        make the next boot's `_arm_from_config` fail the same way with no
        user around to see why.
        """
        result = self._dispatcher.dispatch(
            ArmStrategyCommandHandler, ArmStrategyCommand(self.build_config())
        )
        if result.armed:
            self._store.save(self.build_config())
        return result

    def disarm(self) -> DisarmStrategyResult:
        return self._dispatcher.dispatch(
            DisarmStrategyCommandHandler, DisarmStrategyCommand()
        )

    def armed_summary(self, config: LiveStrategyConfig | None) -> str:
        """One line describing what is actually running, or "" for nothing.

        @details Includes the parameters, not just the strategy name: two
        armings of the same strategy with different periods are different
        bots, and a summary that could not tell them apart would be the
        `armedSummary`-shaped version of the untruthful UI this epic set
        out to fix.
        """
        if config is None:
            return ""
        parts = [
            humanize_strategy_key(config.strategy_key),
            f"{config.symbol} {config.interval}",
            f"{config.sizing_percent:g}%/order",
            f"{config.leverage:g}x",
        ]
        if config.strategy_params:
            parts.append(
                ", ".join(
                    f"{name}={value}"
                    for name, value in sorted(config.strategy_params.items())
                )
            )
        return " · ".join(parts)
