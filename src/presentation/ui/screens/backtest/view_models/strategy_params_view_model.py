"""`EPIC-003F2` — the Backtest screen's strategy selection and
"Thông số Chiến lược" state, lifted out of `BackTestViewModel`.

@details Second slice of `EPIC-003F`, following `003F1`'s trade-log slice
and its rules exactly: this class owns the state, `BackTestViewModel`
forwards to it, and **no call site changes**. The proof that the forward
is faithful is that `tests/` needs no edit at all.

@par What is here, and what deliberately is not
Only state and the signals that state emits. The screen's
`openStrategyPickerRequested` / `openBotParamsRequested` stay on
`BackTestViewModel`: they belong to its block of ten "open a modal"
signals, and pulling two out of that block to satisfy a name prefix would
trade one cohesion for a worse one. Same for the save-request signals
(`botParamsSaveRequested`, `strategyPropertiesSaveRequested`,
`strategyPropertiesCommitRequested`) — those are emitted by dialog-facing
`Slot`s on the facade and carry user intent, not state.

@par Same shape as the Trading screen's card
`EPIC-022C` moved `build_bot_params_schema`/`build_bot_params_rows`/
`parse_bot_params` into `components/strategy_params/` so both screens
compute the form identically. This class is the Backtest side of that
symmetry; whoever eventually shares a single strategy-params ViewModel
between the two screens needs both halves to look like each other first.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.strategy.ui.strategy_params import (
    step_numeric_param_value,
)


class StrategyParamsViewModel(QObject):
    """@brief Which strategy is selected, and the parameter form for it."""

    strategyOptionsChanged = Signal()
    selectedStrategyKeyChanged = Signal()
    #: Fires whenever `botParamsSchema` changes (selected strategy changed,
    #: or a save just refreshed the shown "value"s) — BOT-047.
    botParamsSchemaChanged = Signal()
    botParamsRowsChanged = Signal()
    #: Empty string means "no error". Set by the Presenter after a save
    #: attempt; the modal shows this inline rather than closing.
    botParamsErrorChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._strategy_options: list[dict[str, str]] = []
        self._selected_strategy_key = ""
        self._bot_params_schema: list[dict] = []
        self._bot_params_rows: list[dict[str, object]] = []
        self._bot_params_error = ""

    # ------------------------------------------------------------------ #
    # Strategy selection
    # ------------------------------------------------------------------ #

    def _get_strategy_options(self) -> list[dict[str, str]]:
        return self._strategy_options

    strategyOptions = Property(
        "QVariantList", _get_strategy_options, notify=strategyOptionsChanged
    )

    @Slot(list)
    def set_strategy_options(self, options: list[dict[str, str]]) -> None:
        self._strategy_options = options
        self.strategyOptionsChanged.emit()
        if options and not self._selected_strategy_key:
            self._set_selected_strategy_key(options[0]["key"])

    def _get_selected_strategy_key(self) -> str:
        return self._selected_strategy_key

    def _set_selected_strategy_key(self, value: str) -> None:
        if value != self._selected_strategy_key:
            self._selected_strategy_key = value
            self.selectedStrategyKeyChanged.emit()

    selectedStrategyKey = Property(
        str,
        _get_selected_strategy_key,
        _set_selected_strategy_key,
        notify=selectedStrategyKeyChanged,
    )

    def _get_selected_strategy_name(self) -> str:
        for opt in self._strategy_options:
            if opt.get("key") == self._selected_strategy_key:
                return opt.get("name", self._selected_strategy_key)
        return self._selected_strategy_key or "Select strategy"

    selectedStrategyName = Property(
        str,
        _get_selected_strategy_name,
        notify=selectedStrategyKeyChanged,
    )

    # ------------------------------------------------------------------ #
    # "Thông số Chiến lược"
    # ------------------------------------------------------------------ #

    def _get_bot_params_schema(self) -> list[dict]:
        return self._bot_params_schema

    #: The strategy's own declared inputs, grouped
    #: (`bot_params_form.build_bot_params_schema`). Read-only from the
    #: dialog: the form renders `botParamsRows`, this is what
    #: `step_bot_param_value()` clamps against.
    botParamsSchema = Property(
        "QVariantList", _get_bot_params_schema, notify=botParamsSchemaChanged
    )

    def _get_bot_params_rows(self) -> list[dict[str, object]]:
        return self._bot_params_rows

    #: Flat, ready-to-render presentation rows.
    botParamsRows = Property(
        "QVariantList", _get_bot_params_rows, notify=botParamsRowsChanged
    )

    @Slot(list)
    def set_bot_params_schema(self, schema: list[dict]) -> None:
        self._bot_params_schema = schema
        self.botParamsSchemaChanged.emit()

    @Slot(list)
    def set_bot_params_rows(self, rows: list[dict[str, object]]) -> None:
        self._bot_params_rows = rows
        self.botParamsRowsChanged.emit()

    @Slot(str, str, int, result=str)
    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """Normalise a numeric step against the current schema in Python.

        @details Lives with `_bot_params_schema` rather than on the facade:
        it reads nothing else, and splitting the two would give the clamp
        rule a second place to disagree with the schema it clamps against.
        """
        for group in self._bot_params_schema:
            fields = group.get("fields", [])
            for field in fields:
                if field.get("name") == field_name:
                    return step_numeric_param_value(field, raw_value, direction)
        return raw_value

    def _get_bot_params_error(self) -> str:
        return self._bot_params_error

    botParamsError = Property(str, _get_bot_params_error, notify=botParamsErrorChanged)

    @Slot(str)
    def set_bot_params_error(self, message: str) -> None:
        if message != self._bot_params_error:
            self._bot_params_error = message
            self.botParamsErrorChanged.emit()
