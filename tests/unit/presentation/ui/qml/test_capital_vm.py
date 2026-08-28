"""`CapitalVM` — the BUG-064 shape, tested with no GUI.

The widget version needed `textChanged` wired to the screen,
`capitalValidationMessageChanged` wired back, and a `_sync_validation()`
method holding the label and the Apply button in agreement — three places for
two things to disagree. Here the agreement is one derived property, and these
tests pin it without a dialog, a screen, or a backtest engine.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.Capital.capital_vm import (
    CapitalVM,
)


def _vm(text="10000", currency="USDT"):
    return CapitalVM(
        currencies=["USDT", "BTC"],
        get_text=lambda: text,
        get_currency=lambda: currency,
    )


def test_refresh_pulls_the_screens_current_values():
    vm = _vm(text="250", currency="BTC")
    vm.refresh()

    assert vm.text == "250"
    assert vm.currency == "BTC"


def test_editing_the_amount_asks_for_validation():
    """The presenter owns validation; the widget only has to ask."""
    vm = _vm()
    asked: list[str] = []
    vm.validationRequested.connect(asked.append)

    vm.text = "123"

    assert asked == ["123"]


def test_setting_the_same_amount_does_not_re_ask():
    vm = _vm()
    vm.text = "123"
    asked: list[str] = []
    vm.validationRequested.connect(asked.append)

    vm.text = "123"

    assert asked == []


def test_can_apply_is_derived_from_the_verdict_not_stored():
    vm = _vm()
    assert vm.canApply is True

    vm.setValidationMessage("Vốn phải lớn hơn 0")
    assert vm.canApply is False

    vm.setValidationMessage("")
    assert vm.canApply is True


def test_applying_while_invalid_does_nothing():
    """Not left to the QML `enabled:` binding. A rule held only by a binding
    is a rule that stops existing the moment someone edits that `.qml`."""
    vm = _vm()
    vm.setValidationMessage("Vốn phải lớn hơn 0")
    applied: list[tuple[str, str]] = []
    vm.applied.connect(lambda t, c: applied.append((t, c)))

    vm.apply()

    assert applied == []


def test_applying_when_valid_hands_over_both_values():
    vm = _vm(text="500", currency="BTC")
    vm.refresh()
    applied: list[tuple[str, str]] = []
    vm.applied.connect(lambda t, c: applied.append((t, c)))

    vm.apply()

    assert applied == [("500", "BTC")]


def test_the_verdict_announces_itself_once_per_change():
    """QML binds `visible:` and `enabled:` to this; a missed signal leaves a
    stale error message on screen."""
    vm = _vm()
    fired: list[int] = []
    vm.validationChanged.connect(lambda: fired.append(1))

    vm.setValidationMessage("sai")
    vm.setValidationMessage("sai")
    vm.setValidationMessage("")

    assert fired == [1, 1]


def test_currencies_are_exposed_as_a_plain_list():
    assert _vm().currencies == ["USDT", "BTC"]
