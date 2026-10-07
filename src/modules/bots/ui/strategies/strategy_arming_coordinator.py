"""`EPIC-022D`/`EPIC-022F`/`EPIC-023C` — arming a venue's live strategy,
minus the widgets; in the Bots mode since `EPIC-033K` stage 3.

@details Holds the parameter values the person is editing, turns Arm strategy
and Disarm strategy into a request through `IStrategyArmingControl`, and
reads what strategies exist and their parameter forms through
`IStrategyCatalogReader`. It talks to trading-owned ports only
(`ArmedStrategyConfig` in, `ArmedStrategyConfig` out), never the strategy
module's own (`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8), which is why it can live in `bots/ui/`: `bots` reaches `trading` through
its contracts like any other customer.

@par Why it moved here
HLD §11.2 decided that a strategy armed on a venue is a row in the Bots mode
until `EPIC-029L` makes it a bot kind, and that Trade stays manual. The
desks' strategy cards went, and their coordinator came here with the one
owner left (`VenueStrategies`). It stays one shared class rather than a copy
per venue: `test_presenter_duplication_only_shrinks.py` measured the copies
once (32 → 63 duplicated members, `EPIC-025` PR 4.3m).

Per `async-ui-action-rule.md` §2, this Coordinator owns **no** action-id or
FSM bookkeeping: its owner keeps the `ActionOwnershipTracker` and hands it in.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.arm_block_messages import (
    ARM_BLOCK_MESSAGES,
    DISARM_BLOCKED_MESSAGE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

logger = logging.getLogger("App.StrategyArming")

_ARM_CAUSE = "bots.strategy.arm"
_DISARM_CAUSE = "bots.strategy.disarm"


class StrategyFormState(Protocol):
    """What the arming Coordinator reads from and writes to.

    @details Narrower than its owner's form on purpose: the symbol and the
    sizing the dialog edits are read by `build_config`'s caller-given
    `get_active_symbol` and by these attributes, and naming only what is
    used is what makes that reviewable.
    """

    selected_strategy_key: str
    live_interval: str
    sizing_percent: float
    leverage: float

    def set_strategy_options(
        self,
        strategy_options: Sequence[tuple[str, str]],
        interval_options: Sequence[str],
    ) -> None: ...

    def set_strategy_selection(
        self, strategy_key: str, interval: str, sizing_percent: float, leverage: float
    ) -> None: ...

    def set_bot_params(self, groups: tuple[ParamGroup, ...]) -> None: ...

    def set_bot_params_error(self, message: str) -> None: ...


class StrategyArmingCoordinator:
    """@brief Strategy selection, parameters, arming and persistence for
    the screen it is constructed for."""

    def __init__(
        self,
        view_model: StrategyFormState,
        catalog: IStrategyCatalogReader,
        arming: IStrategyArmingControl,
        get_active_symbol: Callable[[], str],
        get_armed_config: Callable[[], ArmedStrategyConfig | None],
        tracker: ActionOwnershipTracker,
        arm_action_kind: str,
        set_status: Callable[[str, bool], None],
        notifier: INotifier,
        append_log: Callable[[str], None],
        on_armed_changed: Callable[[ArmedStrategyConfig | None, bool], None],
    ) -> None:
        self._view_model = view_model
        self._catalog = catalog
        self._arming = arming
        self._get_active_symbol = get_active_symbol
        self._get_armed_config = get_armed_config
        #: Owned by the constructing Presenter, handed in — never minted
        #: here (`async-ui-action-rule.md` §2).
        self._tracker = tracker
        self._arm_action_kind = arm_action_kind
        self._set_status = set_status
        self._notifier = notifier
        self._append_log = append_log
        self._on_armed_changed = on_armed_changed
        self._params: dict[str, Any] = {}
        #: Sentinel for "the form has never been built", distinct from
        #: `""` which legitimately means "no strategy is picked".
        self._last_form_strategy_key = "\x00never-built"

    # ------------------------------------------------------------------ #
    # Restore (`EPIC-022F`)
    # ------------------------------------------------------------------ #

    def restore_into_view_model(self, interval_options: list[str]) -> None:
        """Fills the card from the saved selection — and does nothing else.

        @details No arm request, no `EnsureSessionReadyCommand`, no network
        call. `BUG-101` (a Backtest restore that fired a real 200k-row
        query because it went through the same setters a user does) and
        `BUG-104` (a remembered route that started a live stream on boot)
        are the same bug twice; this method is written to not be its third
        occurrence. After a restore the screen shows the saved choice and
        nothing is armed, so the user still has to press "Nạp chiến lược"
        themselves.

        `IStrategyArmingControl.saved_selection()` never raises — an invalid
        saved config restores as "nothing selected" inside the port itself.
        """
        options = self._catalog.options()
        self._view_model.set_strategy_options(
            [(opt.key, opt.label) for opt in options], interval_options
        )
        saved = self._arming.saved_selection()

        saved_key = saved.strategy_key
        available_keys = [opt.key for opt in options]
        if saved_key not in available_keys:
            # A saved key that no longer exists (renamed, removed) must
            # not be shown as if it were selectable. The combo falls back
            # to the first real strategy so the card is never empty — but
            # nothing is armed either way, so the fallback can only ever
            # become live if the user presses "Nạp chiến lược" on it.
            saved_key = available_keys[0] if available_keys else ""
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
        key = self._view_model.selected_strategy_key
        if not key:
            self._view_model.set_bot_params(())
            return
        try:
            groups = self._catalog.params_form(key, self._params)
        except KeyError:
            self._view_model.set_bot_params(())
            return
        self._view_model.set_bot_params(groups)
        self._view_model.set_bot_params_error("")

    def apply_params(self, raw_values: Mapping[str, Any]) -> bool:
        """@returns Whether the values were accepted.

        @details Validation is `IStrategyCatalogReader.validate_params()` against
        the strategy's own declared inputs — the same call the Backtest
        screen makes, so a value accepted on one screen cannot be rejected
        on the other.
        """
        key = self._view_model.selected_strategy_key
        if not key:
            return False
        result = self._catalog.validate_params(key, raw_values)
        if not result.accepted:
            self._view_model.set_bot_params_error(result.error)
            return False
        self._params = dict(result.values)
        self._view_model.set_bot_params_error("")
        self.refresh_params_rows()
        return True

    # ------------------------------------------------------------------ #
    # Arm / disarm
    # ------------------------------------------------------------------ #

    def build_config(self) -> ArmedStrategyConfig:
        return ArmedStrategyConfig(
            strategy_key=self._view_model.selected_strategy_key,
            symbol=self._get_active_symbol(),
            interval=self._view_model.live_interval,
            strategy_params=dict(self._params),
            sizing_percent=self._view_model.sizing_percent,
            leverage=self._view_model.leverage,
        )

    def on_arm_clicked(self) -> None:
        """The "Nạp chiến lược" button, end to end.

        Action ownership stays the Presenter's: it owns the tracker and
        hands it in, which `async-ui-action-rule.md` §2 explicitly sanctions
        ("a single shared tracker the Presenter owns and hands to every
        Coordinator") and distinguishes from a Coordinator minting its own
        action ids.
        """
        action = self._tracker.begin_action(self._arm_action_kind, None, None)
        self._report_state(busy=True)
        try:
            result = self.arm()
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            self._tracker.finish_action(action.action_id, ActionOutcome.FAILED)
            self._report_state(busy=False)
            self._command_failed(
                _ARM_CAUSE,
                "The strategy could not be armed. Check the venue and try again.",
                failure_detail(exc),
            )
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

        # `EnumLabels` is a total mapping, so every member has a line by
        # construction. What it cannot cover is `None`:
        # `ArmStrategyCommandHandler` gives a reason to every `armed=False`
        # result it returns, but `ArmStrategyResult.block_reason` is
        # declared optional because the armed case has none, so the
        # invariant lives in the handler rather than in the type.
        reason = result.block_reason
        message = (
            ARM_BLOCK_MESSAGES[reason]
            if reason is not None
            else "Strategy could not be armed (no reason reported)."
        )
        self._command_failed(_ARM_CAUSE, message, result.error_message or "")

    def on_disarm_clicked(self) -> None:
        """The "Gỡ" button, end to end."""
        try:
            result = self.disarm()
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            self._command_failed(
                _DISARM_CAUSE,
                "The strategy could not be removed. Check the venue and try again.",
                failure_detail(exc),
            )
            return
        self._report_state(busy=False)
        if result.disarmed:
            self._set_status("Strategy removed.", False)
        else:
            self._command_failed(_DISARM_CAUSE, DISARM_BLOCKED_MESSAGE)

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
        key = self._view_model.selected_strategy_key
        if key == self._last_form_strategy_key:
            return
        self._last_form_strategy_key = key
        self.refresh_params_rows()

    def _command_failed(self, cause: str, headline: str, detail: str = "") -> None:
        """A command the user ran did not happen (`BOT-169`): a message box,
        the technical text behind its Details."""
        self._notifier.report_failure(
            FailureNotice(FailureKind.COMMAND, cause, headline, detail=detail)
        )

    def _report_state(self, *, busy: bool) -> None:
        """Pushes what the SESSION says is armed, never what the combo
        shows — the two differ on purpose between picking and arming."""
        self._on_armed_changed(self._get_armed_config(), busy)

    def arm(self) -> ArmStrategyResult:
        """Runs the arm request through `IStrategyArmingControl`; persistence
        on a successful arm now happens inside the port's own implementation
        (`EPIC-025` PR 4.3m O6) rather than here."""
        return self._arming.arm(self.build_config())

    def disarm(self) -> DisarmStrategyResult:
        return self._arming.disarm()

    def armed_summary(self, config: ArmedStrategyConfig | None) -> str:
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
            self._label_for(config.strategy_key),
            f"{config.symbol} {config.interval}",
            f"{write_value(ColumnKind.PERCENT, config.sizing_percent)}/order",
            f"{write_value(ColumnKind.QUANTITY, config.leverage)}x",
        ]
        if config.strategy_params:
            parts.append(
                ", ".join(
                    f"{name}={value}"
                    for name, value in sorted(config.strategy_params.items())
                )
            )
        return " · ".join(parts)

    def _label_for(self, key: str) -> str:
        """`options()` already returns each key's display label —
        `strategy_display.humanize_strategy_key` stops crossing (ADR §5).
        A key an armed config still names but `options()` no longer lists
        (renamed/removed since arming) falls back to the raw key rather
        than crashing."""
        for option in self._catalog.options():
            if option.key == key:
                return option.label
        return key
