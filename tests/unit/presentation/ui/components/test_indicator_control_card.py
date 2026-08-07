from Binace_Bot.src.presentation.ui.components.indicator_control_card import (
    IndicatorControlCard,
)


def test_indicator_control_card_defaults_to_all_disabled(qapp):
    card = IndicatorControlCard()

    assert card.chk_rsi.isChecked() is False
    assert card.chk_ema.isChecked() is False
    assert card.chk_macd.isChecked() is False


def test_indicator_control_card_default_periods(qapp):
    card = IndicatorControlCard()

    assert card.spin_rsi_period.value() == 14
    assert card.spin_ema_period.value() == 20


def test_indicator_control_card_checkboxes_and_periods_are_settable(qapp):
    card = IndicatorControlCard()

    card.chk_rsi.setChecked(True)
    card.spin_rsi_period.setValue(21)
    card.chk_ema.setChecked(True)
    card.spin_ema_period.setValue(50)
    card.chk_macd.setChecked(True)

    assert card.chk_rsi.isChecked() is True
    assert card.spin_rsi_period.value() == 21
    assert card.chk_ema.isChecked() is True
    assert card.spin_ema_period.value() == 50
    assert card.chk_macd.isChecked() is True
