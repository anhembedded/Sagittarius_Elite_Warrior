"""`EPIC-033K` stage 3 — Bots → Arm strategy…'s dialog: the desks' strategy
card as a dialog, plus the symbol the card took from its desk's chart.

It shows the venue's form, sends each edit back to it, and only Arm strategy
accepts; Cancel is the default (`ui-presentation-rule.md` §7). Leverage is
not offered on Spot (`EPIC-027O` AC3).
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.arm_strategy_dialog import (
    ARM_TEXT,
    ArmStrategyDialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_form_view_model import (
    StrategyFormViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_KEYS = (("ema_crossover", "EMA crossover"), ("rsi_revert", "RSI revert"))


def _form() -> StrategyFormViewModel:
    form = StrategyFormViewModel()
    form.set_strategy_options(_KEYS, ("1m", "15m", "1h"))
    form.set_strategy_selection("rsi_revert", "15m", 5.0, 3.0)
    form.set_symbol("ETHUSDT", ("BTCUSDT", "ETHUSDT"))
    return form


@pytest.fixture
def form() -> StrategyFormViewModel:
    return _form()


def _dialog(
    qtbot, venue: TradingVenue, form: StrategyFormViewModel
) -> ArmStrategyDialog:
    dialog = ArmStrategyDialog(venue, form)
    qtbot.addWidget(dialog)
    return dialog


def _leverage_shown(dialog: ArmStrategyDialog) -> bool:
    fields = dialog.findChild(QFormLayout)
    return fields.isRowVisible(dialog.leverage)


def test_the_dialog_shows_the_venues_form(qtbot, form) -> None:
    dialog = _dialog(qtbot, TradingVenue.FUTURES_TESTNET, form)

    assert dialog.windowTitle() == "Arm Strategy"
    assert dialog.strategy.currentData() == "rsi_revert"
    assert dialog.symbol.currentText() == "ETHUSDT"
    assert dialog.interval.currentText() == "15m"
    assert (dialog.sizing.value(), dialog.leverage.value()) == (5.0, 3.0)


def test_each_edit_reaches_the_form_and_arms_nothing(qtbot, form) -> None:
    dialog = _dialog(qtbot, TradingVenue.FUTURES_TESTNET, form)
    changed: list[bool] = []
    form.strategy_changed.connect(lambda: changed.append(True))

    dialog.strategy.setCurrentIndex(dialog.strategy.findData("ema_crossover"))
    dialog.symbol.setCurrentText("BTCUSDT")
    dialog.interval.setCurrentText("1h")
    dialog.sizing.setValue(7.0)
    dialog.leverage.setValue(10.0)

    assert form.selected_strategy_key == "ema_crossover"
    assert changed == [True]
    assert (form.selected_symbol, form.live_interval) == ("BTCUSDT", "1h")
    assert (form.sizing_percent, form.leverage) == (7.0, 10.0)
    assert dialog.result() == 0


def test_cancel_is_the_default_and_arm_strategy_accepts(qtbot, form) -> None:
    dialog = _dialog(qtbot, TradingVenue.SPOT_TESTNET, form)
    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)

    assert cancel.isDefault() and not dialog.arm.isDefault()
    assert dialog.arm.text() == ARM_TEXT
    dialog.arm.click()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_leverage_is_offered_on_futures_and_not_on_spot(qtbot) -> None:
    assert _leverage_shown(_dialog(qtbot, TradingVenue.FUTURES_TESTNET, _form()))
    assert not _leverage_shown(_dialog(qtbot, TradingVenue.SPOT_TESTNET, _form()))


def test_a_saved_symbol_missing_from_the_list_is_offered_first() -> None:
    form = StrategyFormViewModel()

    form.set_symbol("SOLUSDT", ("BTCUSDT", "ETHUSDT"))

    assert form.symbol_options == ("SOLUSDT", "BTCUSDT", "ETHUSDT")
    assert form.selected_symbol == "SOLUSDT"


def test_only_a_listed_symbol_can_be_chosen(qtbot, form) -> None:
    """PR #376 review: a typed `BTCUSDX` was armed and read "Armed"."""
    dialog = _dialog(qtbot, TradingVenue.FUTURES_TESTNET, form)

    assert not dialog.symbol.isEditable()
    assert [dialog.symbol.itemText(i) for i in range(dialog.symbol.count())] == [
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_a_first_arming_sends_the_timeframe_and_strategy_it_shows(qtbot) -> None:
    """PR #376 review: with nothing saved the form held no timeframe while
    the dialog showed `1m`, and the session refused the arm."""
    form = StrategyFormViewModel()
    form.set_strategy_options(_KEYS, ("1m", "15m"))
    form.set_strategy_selection("", "", 1.0, 1.0)
    form.set_symbol("", ("BTCUSDT",))

    dialog = _dialog(qtbot, TradingVenue.FUTURES_TESTNET, form)

    assert form.live_interval == dialog.interval.currentText() == "1m"
    assert (
        form.selected_strategy_key == dialog.strategy.currentData() == "ema_crossover"
    )
    assert form.selected_symbol == "BTCUSDT"
