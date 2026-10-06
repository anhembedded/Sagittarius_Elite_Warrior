"""`ParamsSink` — one strategy's parameter groups, as `StrategyParamsDialog`
reads and saves them (`EPIC-033K` stage 3).

The dialog names its view model by `BotParamsSink`, a Protocol written for
the QML-era strategy card, so its members keep that card's camelCase names.
This class is the one implementer a screen owns instead of repeating those
members on its own view model: the Bots mode's arming form holds one, and
keeps its own names snake_case outside this package.

Plausible extensions, each local: the Backtest screen's own copy of these
members could become one of these (one field on its view model).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup

from .numeric_step import step_numeric_param_value


class ParamsSink(QObject):
    """@brief The groups shown, their last error, and the dialog's Save."""

    #: The groups or the error changed: the dialog redraws.
    botParamsChanged = Signal()
    #: The dialog's Save, with the values as typed. Qt takes the type's
    #: *name* at runtime while the PySide6 stub declares `type`.
    botParamsSaveRequested = Signal("QVariantMap")  # type: ignore[arg-type]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.botParamsGroups: tuple[ParamGroup, ...] = ()
        self.botParamsError = ""

    def set_groups(self, groups: tuple[ParamGroup, ...]) -> None:
        self.botParamsGroups = groups
        self.botParamsChanged.emit()

    def set_error(self, message: str) -> None:
        self.botParamsError = message
        self.botParamsChanged.emit()

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """`ParamStepper`: one Up/Down/wheel step, clamped to the field's
        declared range; any other field's value comes back unchanged."""
        for group in self.botParamsGroups:
            for field in group.fields:
                if field.name == field_name:
                    return step_numeric_param_value(field, raw_value, direction)
        return raw_value

    @Slot("QVariantMap")
    def requestBotParamsSave(self, values: dict) -> None:
        self.botParamsSaveRequested.emit(values)
