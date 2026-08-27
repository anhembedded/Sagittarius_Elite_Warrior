"""Strategy parameters, broker properties, capital validation and exchange
order-rule verification for the Backtest screen."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.symbol_market_metadata import (
    MetadataVerificationStatus,
    OrderIntent,
    validate_order_intent,
)

from ..logic.bot_params_form import (
    build_bot_params_rows,
    build_bot_params_schema,
    parse_bot_params,
)
from ..logic.pre_backtest_assertions import (
    PreBacktestAssertionPipeline,
    PreBacktestInput,
)
from ..ports.i_backtest_screen_state import IBacktestScreenState

#: Capital that failed to parse. Verification still runs on it — a blank or
#: mistyped box is not a reason to leave the previous verdict on screen.
_UNPARSEABLE_CAPITAL = 0.0


class StrategyConfigCoordinator:
    """Everything between "the user changed a config field" and "the view
    model reflects it": strategy selection, the bot-params schema, broker
    properties, capital validation, and order-rule verification.

    Deliberately does NOT start runs. Both save handlers used to end by
    dispatching the FSM and kicking off a backtest; that tail stays with the
    presenter, which owns the FSM (`EPIC-003B`'s division). These methods
    return whether a re-run was asked for and let the caller decide.

    Reads `strategy_params`, the symbol, the metadata cache and the raw
    klines through callables: all four are presenter state that changes
    between calls, and several existing tests set them directly.
    """

    def __init__(
        self,
        view_model,
        state: IBacktestScreenState,
        strategy_registry,
        logger,
        get_market_metadata: Callable[[str], Any],
        notify_config_changed: Callable[[], None],
    ) -> None:
        self._view_model = view_model
        self._state = state
        self._strategy_registry = strategy_registry
        self._logger = logger
        self._get_market_metadata = get_market_metadata
        self._notify_config_changed = notify_config_changed

    # ---------------------------------------------------------------- #
    # Strategy selection and parameter schema
    # ---------------------------------------------------------------- #

    def on_strategy_selection_changed(self) -> None:
        """A different strategy has an entirely different parameter schema —
        any values saved for the previous one would either be silently
        ignored or raise "param nobody declares" against the new one, so
        they're discarded rather than carried over (BOT-047)."""
        self._state.strategy_params = None
        self._view_model.set_bot_params_error("")
        self.refresh_bot_params_schema()
        self._logger.log_strategy_selected(
            self._view_model.selectedStrategyName,
            self._view_model.selectedStrategyKey,
        )
        self._notify_config_changed()

    def refresh_bot_params_schema(self) -> None:
        strategy_cls = self._selected_strategy_class()
        schema = (
            build_bot_params_schema(strategy_cls, self._state.strategy_params)
            if strategy_cls is not None
            else []
        )
        self._view_model.set_bot_params_schema(schema)
        self._view_model.set_bot_params_rows(build_bot_params_rows(schema))

    def _selected_strategy_class(self):
        return self._strategy_registry.available().get(
            self._view_model.selectedStrategyKey
        )

    # ---------------------------------------------------------------- #
    # Saving
    # ---------------------------------------------------------------- #

    def apply_bot_params(self, raw_values: dict) -> bool:
        """ "Lưu & Re-Backtest" (BOT-047): validates the modal's values
        against the selected strategy's own declarations before accepting
        anything — an out-of-range/mistyped value must show an inline error
        and leave the modal open, never silently fall back to a default.

        Returns True when the caller should start a re-run.
        """
        strategy_cls = self._selected_strategy_class()
        if strategy_cls is None:
            return False
        try:
            parsed = parse_bot_params(strategy_cls().inputs, raw_values)
            strategy_cls(parsed)  # construct-and-discard: the real validator
        except ValueError as exc:
            self._view_model.set_bot_params_error(str(exc))
            return False

        self._state.strategy_params = parsed
        self._finish_save(parsed)
        return True

    def apply_strategy_properties(self, payload: dict) -> bool:
        """ "Lưu & Chạy lại" (BOT-104): combined Strategy Inputs and Broker
        Properties from StrategyPropertiesModal.

        Returns True when the caller should start a re-run.
        """
        inputs = payload.get("inputs", {})
        props = payload.get("properties", {})

        strategy_cls = self._selected_strategy_class()
        if strategy_cls is not None and inputs:
            try:
                parsed = parse_bot_params(strategy_cls().inputs, inputs)
                strategy_cls(parsed)
                self._state.strategy_params = parsed
            except ValueError as exc:
                self._view_model.set_bot_params_error(str(exc))
                return False

        self._apply_broker_properties(props)
        self._finish_save(self._state.strategy_params or {})
        return True

    #: Broker property key -> (view model attribute, coercion). Table rather
    #: than twelve near-identical `if "x" in props` blocks: a new property is
    #: a row here, and a typo in one of twelve hand-written branches was the
    #: kind of thing nothing would have caught.
    _BROKER_PROPERTIES: tuple[tuple[str, str, Callable[[Any], Any]], ...] = (
        ("initial_capital", "initialCapitalText", str),
        ("currency", "selectedCurrency", str),
        ("order_size_type", "orderSizeType", str),
        ("order_size_text", "orderSizeText", str),
        ("pyramiding", "pyramiding", int),
        ("commission_type", "commissionType", str),
        ("commission_text", "commissionText", str),
        ("slippage_ticks", "slippageTicks", int),
        ("long_leverage", "longLeverage", float),
        ("short_leverage", "shortLeverage", float),
        ("take_profit_enabled", "takeProfitPctEnabled", bool),
        ("take_profit_pct_text", "takeProfitPctText", str),
    )

    def _apply_broker_properties(self, props: dict) -> None:
        for key, attribute, coerce in self._BROKER_PROPERTIES:
            if key in props:
                setattr(self._view_model, attribute, coerce(props[key]))

    def _finish_save(self, saved_params: dict) -> None:
        self._view_model.set_bot_params_error("")
        self.refresh_bot_params_schema()
        self._view_model.botParamsSaved.emit()
        self._logger.log_bot_params_saved(
            self._view_model.selectedStrategyName,
            saved_params,
        )
        self._notify_config_changed()

    # ---------------------------------------------------------------- #
    # Capital and exchange order rules
    # ---------------------------------------------------------------- #

    def on_capital_changed(self) -> None:
        self.set_capital_validation_message(self._view_model.initialCapitalText)
        try:
            capital_val = float(self._view_model.initialCapitalText)
            self._logger.log_capital_updated(
                capital_val,
                self._view_model.selectedCurrency,
            )
        except (ValueError, TypeError):
            pass
        self._notify_config_changed()

    def on_capital_validation_requested(self, value: str) -> None:
        self.set_capital_validation_message(value)

    def set_capital_validation_message(self, value: str) -> None:
        issues = PreBacktestAssertionPipeline.default().validate(
            PreBacktestInput(value, False, "", "")
        )
        self._view_model.set_capital_validation_message(
            issues[0].message if issues else ""
        )
        self.refresh_market_rule_verification()

    def refresh_market_rule_verification(self) -> None:
        """Evaluates whether current symbol and capital comply with exchange
        order rules (BOT-095E1)."""
        metadata = self._get_market_metadata(self._state.symbol)
        try:
            capital_val = float(self._view_model.initialCapitalText)
        except (ValueError, TypeError):
            capital_val = _UNPARSEABLE_CAPITAL

        if metadata is None:
            self._view_model.set_market_rule_verification(
                MetadataVerificationStatus.UNVERIFIED_MISSING.value,
                "Chưa xác minh theo quy tắc sàn (chưa có metadata cho cặp giao dịch).",
            )
            return

        if metadata.is_stale():
            self._view_model.set_market_rule_verification(
                MetadataVerificationStatus.UNVERIFIED_STALE.value,
                f"Chưa xác minh theo quy tắc sàn (metadata cũ từ {metadata.fetched_at.strftime('%Y-%m-%d %H:%M:%S UTC')}).",
            )
            return

        raw_klines = self._state.current_raw_klines
        ref_price = (
            raw_klines[-1].close_price
            if raw_klines
            else metadata.price_filter.min_price
        )
        qty = capital_val / ref_price if ref_price > 0 else 0.0
        intent = OrderIntent(symbol=self._state.symbol, price=ref_price, quantity=qty)
        result = validate_order_intent(intent, metadata)
        self._view_model.set_market_rule_verification(
            result.status.value,
            result.explanation,
        )
