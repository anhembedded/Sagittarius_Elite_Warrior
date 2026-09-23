"""`BOT-063` — the `BotParamsSink` for one indicator script's params dialog.

@details Unlike the live strategy's sink (`StrategyCardViewModel`, one
permanent object whose target key changes as the user picks a different
strategy from a combo), several indicator scripts can be enabled and
independently edited at once, so there is no single "currently selected"
script to hold a sink for. This is instead built fresh per dialog-open,
one per script key (`dev_board_panel.py._open_script_params_dialog()`),
and talks straight to the injected catalog/store rather than round-
tripping through a Presenter signal — nothing else in the UI needs to
react live to a script's params changing (unlike the strategy card's
summary label, which is shown elsewhere on screen), so the extra
indirection would buy nothing here.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
    IndicatorScriptParamsStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form.numeric_step import (
    step_numeric_param_value,
)


class IndicatorScriptParamsSink(QObject):
    """Satisfies `support.ui_kit.param_form.strategy_params_dialog.BotParamsSink`
    structurally for exactly one script key."""

    botParamsChanged = Signal()

    def __init__(
        self,
        catalog: IndicatorScriptCatalog,
        store: IndicatorScriptParamsStore,
        key: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._store = store
        self._key = key
        #: Plain mutable attributes, not `@property` — `BotParamsSink` is a
        #: `Protocol` declaring these as instance attributes, which mypy
        #: reads as read-write; a read-only property fails that structural
        #: check even though `StrategyParamsDialog` only ever reads them.
        self.botParamsError: str = ""
        self.botParamsGroups: tuple[ParamGroup, ...] = self._build_groups()

    def _build_groups(self) -> tuple[ParamGroup, ...]:
        saved = self._store.load_all().get(self._key, {})
        return self._catalog.params_form(self._key, saved)

    def requestBotParamsSave(self, values: dict) -> None:
        """@details On acceptance, persists immediately — there is no
        separate "Arm"/apply step for an indicator script the way there
        is for a live strategy, so Save here means the same thing the
        dialog's button says. Takes effect on the next Load History/Start
        Live, same "no retroactive effect" contract enabling/disabling a
        script already has (`IndicatorScriptListModel`'s own docstring)."""
        result = self._catalog.validate_params(self._key, values)
        if result.error:
            self.botParamsError = result.error
        else:
            self.botParamsError = ""
            self._store.save(self._key, dict(result.values))
            self.botParamsGroups = self._build_groups()
        self.botParamsChanged.emit()

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """`ParamStepper` — mirrors `StrategyCardViewModel.step_bot_param_value`."""
        for group in self.botParamsGroups:
            for field in group.fields:
                if field.name == field_name:
                    return step_numeric_param_value(field, raw_value, direction)
        return raw_value
