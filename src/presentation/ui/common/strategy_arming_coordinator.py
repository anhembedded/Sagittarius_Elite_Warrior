"""`EPIC-022D`/`EPIC-022F`/`EPIC-023C` — a screen's strategy card, minus the
widgets.

@details Holds the parameter values the user is editing, turns the card's
two buttons into an arm/disarm request through `IStrategyArmingControl`, and
reads what strategies exist and their parameter forms through
`IStrategyCatalogReader`.

`EPIC-025` PR 4.3m: neither `trading` nor `dashboard` imports
`modules.strategy.ui.*` or `modules.strategy.application.services.
strategy_registry` directly any more (`architecture-rule.md` §3 forbids it
the moment `strategy` becomes a module in PR 4.4). What crossed as
`StrategyRegistry.available()`, `build_bot_params_schema`/
`build_bot_params_rows`/`parse_bot_params` and a direct
`dispatcher.dispatch(ArmStrategyCommandHandler, …)` +
`LiveStrategyConfigStore` now crosses as two published ports —
`IStrategyCatalog` and `IStrategyArming` — with the class-handling and the
persistence both kept inside `modules/strategy`
(`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§5).

**PR 4.4c (§8) inverts those two ports again**, this time so `trading` (this
file's own future home once it moves with the screens) never has to import
`modules.strategy.contracts` at all: `trading` now declares its own
`IStrategyCatalogReader`/`IStrategyArmingControl` (`modules/trading/
contracts/`), and `strategy`'s adapter implements them by wrapping the
original `IStrategyCatalog`/`IStrategyArming` and translating field for
field at the boundary. This file talks to the trading-owned ports only —
`ArmedStrategyConfig` in, `ArmedStrategyConfig` out — never the strategy-owned
ones underneath.

**This file stays shared rather than becoming two per-screen copies.** An
earlier PR 4.3m draft gave Trading and Dev Board a byte-identical copy
each, reasoning that the ADR's §5 crossing table had put every piece of
*data* on the port, leaving only "orchestration glue with nothing
behavioural to duplicate wrongly" — a claim
`tests/unit/architecture/test_presenter_duplication_only_shrinks.py`
disproved by measurement (32 → 63 duplicated members): the glue's own
method names are exactly what that ratchet counts, data or not. This is
also where the class lived before `EPIC-025` PR 2.1e ever moved it into
`modules/strategy/ui/` (`git log --follow` on this path shows the same
`presentation/ui/common/strategy_arming_coordinator.py` name), so
un-crossing the module boundary and re-sharing the file are the same
move, not two.

Per `async-ui-action-rule.md` §2, this Coordinator owns **no** action-id or
FSM bookkeeping: the owning Presenter keeps its own `ActionOwnershipTracker`
and hands it in.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
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
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

logger = logging.getLogger("App.StrategyArming")

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
        ArmStrategyBlockReason.SYMBOL_LEASED: (
            "This symbol is already being managed by another strategy — "
            "remove that one first, or choose a different symbol."
        ),
    },
)
DISARM_BLOCKED_MESSAGE = (
    "Trading is active — turn off trading before removing the strategy."
)


class StrategyCardViewModel(Protocol):
    """What the strategy card's Coordinator reads from and writes to.

    @details Narrower than either screen's own ViewModel on purpose: this
    Coordinator has no business touching the toggle, the chart, or the
    session stats that ViewModel also carries, and naming only what it
    uses is what makes that reviewable.
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

    def set_bot_params(self, groups: tuple[ParamGroup, ...]) -> None: ...

    def set_bot_params_error(self, message: str) -> None: ...

    def set_last_signal_text(self, text: str) -> None: ...


class StrategyArmingCoordinator:
    """@brief Strategy selection, parameters, arming and persistence for
    the screen it is constructed for."""

    def __init__(
        self,
        view_model: StrategyCardViewModel,
        catalog: IStrategyCatalogReader,
        arming: IStrategyArmingControl,
        get_active_symbol: Callable[[], str],
        get_armed_config: Callable[[], ArmedStrategyConfig | None],
        tracker: ActionOwnershipTracker,
        arm_action_kind: str,
        set_status: Callable[[str, bool], None],
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

        @details No arm request, no `EnableTradingCommand`, no network
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
            [{"key": opt.key, "label": opt.label} for opt in options],
            interval_options,
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
        key = self._view_model.selectedStrategyKey
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
        key = self._view_model.selectedStrategyKey
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
            strategy_key=self._view_model.selectedStrategyKey,
            symbol=self._get_active_symbol(),
            interval=self._view_model.liveInterval,
            strategy_params=dict(self._params),
            sizing_percent=self._view_model.sizingPercent,
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

    def on_signal_generated(self, event: Any) -> None:
        """`SignalFeed.signalGenerated`'s handler — connected directly to
        that signal by the constructing Presenter, so `TradingPresenter`
        and `DashboardPresenter` need no `_on_signal_generated` method of
        their own to define identically (`tests/unit/architecture/
        test_presenter_duplication_only_shrinks.py`).

        Filtered to the armed symbol on purpose: `SignalGeneratedEvent`
        goes out on the same `IEventBus` a *backtest* run's own
        `StrategyEngine` publishes on, and an unfiltered card would show a
        backtest's output as if it were live.
        """
        signal = getattr(event, "signal", None)
        if signal is None:
            return
        config = self._get_armed_config()
        if config is None or signal.symbol != config.symbol:
            return
        action = getattr(signal.action, "value", str(signal.action))
        when = signal.time.strftime("%H:%M:%S")
        self._view_model.set_last_signal_text(
            f"{when} · {action} @ {signal.price:g} — {signal.reason}"
        )

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
