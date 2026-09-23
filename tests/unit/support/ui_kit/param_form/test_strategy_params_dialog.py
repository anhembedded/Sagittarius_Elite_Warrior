"""`BOT-063` — the two additions `StrategyParamsDialog` needed to be
reusable for the Dev Board's per-script params modal: an overridable
title, and a "Restore Defaults" button. No test previously exercised this
dialog directly."""

from __future__ import annotations

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import (
    ParamField,
    ParamGroup,
    ParamKind,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form.strategy_params_dialog import (
    StrategyParamsDialog,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakeSink(QWidget):
    """Satisfies `BotParamsSink` structurally: a real `QObject` (via
    `QWidget`) so `botParamsChanged` is a real bound `Signal`, plus
    `step_bot_param_value` for `ParamStepper`."""

    botParamsChanged = Signal()  # noqa: N815 - BotParamsSink's own PySide6 spelling

    def __init__(self, groups: tuple[ParamGroup, ...]) -> None:
        super().__init__()
        self.botParamsGroups = groups
        self.botParamsError = ""
        self.saved_values: dict | None = None

    def requestBotParamsSave(self, values: dict) -> None:  # noqa: N802 - see above
        self.saved_values = values

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        return raw_value


def _int_group(name: str, default: int, current: int) -> tuple[ParamGroup, ...]:
    field = ParamField(
        name=name, label=name, kind=ParamKind.INT, default=default, value=current
    )
    return (ParamGroup(label="", fields=(field,)),)


def test_default_title_is_unchanged_for_existing_callers(qapp):
    sink = _FakeSink(_int_group("period", 20, 20))
    dialog = StrategyParamsDialog(sink)

    assert dialog.title == "Strategy Parameters"


def test_title_can_be_overridden(qapp):
    sink = _FakeSink(_int_group("period", 20, 20))
    dialog = StrategyParamsDialog(sink, title="Indicator Parameters")

    assert dialog.title == "Indicator Parameters"


def test_restore_defaults_resets_a_changed_field_without_saving(qapp):
    sink = _FakeSink(_int_group("period", 20, 99))
    dialog = StrategyParamsDialog(sink)
    assert dialog.collect_values() == {"period": "99"}

    dialog._on_restore_clicked()

    assert dialog.collect_values() == {"period": "20"}
    assert sink.saved_values is None
