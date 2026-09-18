"""`EPIC-003F4` — `BrokerSimViewModel` on its own.

The clamps are the reason this file exists. Every one of them is a
guard against a run whose numbers cannot happen at a real broker:
zero orders per signal, negative commission, negative slippage,
sub-1x leverage.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.broker_sim_view_model import (
    DEFAULT_COMMISSION_TEXT,
    DEFAULT_COMMISSION_VALUE,
    DEFAULT_ORDER_SIZE_TEXT,
    DEFAULT_ORDER_SIZE_VALUE,
    MIN_COMMISSION_VALUE,
    MIN_LEVERAGE,
    MIN_PYRAMIDING,
    MIN_SLIPPAGE_TICKS,
    BrokerSimViewModel,
)


def test_defaults_match_the_shipped_broker_defaults(qapp) -> None:
    vm = BrokerSimViewModel()

    assert vm.orderSizeValue == DEFAULT_ORDER_SIZE_VALUE
    assert vm.orderSizeText == DEFAULT_ORDER_SIZE_TEXT
    assert vm.commissionValue == DEFAULT_COMMISSION_VALUE
    assert vm.commissionText == DEFAULT_COMMISSION_TEXT
    assert vm.pyramiding == MIN_PYRAMIDING
    assert vm.slippageTicks == MIN_SLIPPAGE_TICKS
    assert vm.longLeverage == MIN_LEVERAGE
    assert vm.shortLeverage == MIN_LEVERAGE
    assert vm.takeProfitPctEnabled is False


@pytest.mark.parametrize(
    ("setter", "reader", "attempted", "clamped"),
    [
        ("set_pyramiding", "pyramiding", 0, MIN_PYRAMIDING),
        ("set_pyramiding", "pyramiding", -5, MIN_PYRAMIDING),
        ("set_commission_value", "commissionValue", -0.5, MIN_COMMISSION_VALUE),
        ("set_slippage_ticks", "slippageTicks", -3, MIN_SLIPPAGE_TICKS),
        ("set_long_leverage", "longLeverage", 0.0, MIN_LEVERAGE),
        ("set_short_leverage", "shortLeverage", 0.5, MIN_LEVERAGE),
    ],
)
def test_impossible_broker_values_are_clamped_not_stored(
    qapp, setter: str, reader: str, attempted: float, clamped: float
) -> None:
    """A run configured with 0x leverage or a negative fee reports a
    profit no broker would have paid — the clamp is what keeps the
    result honest (`domain-truth-rule.md`)."""
    vm = BrokerSimViewModel()

    getattr(vm, setter)(attempted)

    assert getattr(vm, reader) == clamped


def test_typing_a_number_updates_both_the_text_and_the_parsed_value(qapp) -> None:
    vm = BrokerSimViewModel()

    vm.set_order_size_text("250.5")

    assert vm.orderSizeText == "250.5"
    assert vm.orderSizeValue == 250.5


def test_a_half_typed_number_keeps_the_text_and_the_last_good_value(qapp) -> None:
    """An empty field is what the user has typed so far, not a request to
    size orders at nothing — the field must show it while the value stays
    put until a full number arrives.

    (`"0."` is NOT such a case: `float("0.")` is `0.0`, so that keystroke
    really does set the value to zero. Written that way first, and the
    test caught it.)"""
    vm = BrokerSimViewModel()
    vm.set_order_size_text("250")

    vm.set_order_size_text("")

    assert vm.orderSizeText == ""
    assert vm.orderSizeValue == 250.0


def test_typing_commission_text_emits_both_of_its_signals(qapp) -> None:
    """Two separate readers: the dialog shows `commissionText`, the run
    config reads `commissionValue`. A single emit would leave one of them
    stale."""
    vm = BrokerSimViewModel()
    seen: list[str] = []
    vm.commissionTextChanged.connect(lambda: seen.append("text"))
    vm.commissionValueChanged.connect(lambda: seen.append("value"))

    vm.set_commission_text("0.075")

    assert seen == ["text", "value"]
    assert vm.commissionValue == 0.075


def test_setting_the_same_value_twice_emits_once(qapp) -> None:
    vm = BrokerSimViewModel()
    seen: list[str] = []
    vm.pyramidingChanged.connect(lambda: seen.append("pyramiding"))

    vm.set_pyramiding(3)
    vm.set_pyramiding(3)

    assert seen == ["pyramiding"]
