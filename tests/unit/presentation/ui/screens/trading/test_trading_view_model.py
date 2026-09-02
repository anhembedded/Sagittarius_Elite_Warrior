from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_view_model import (
    TradingViewModel,
)


def test_starts_disabled_and_idle(qapp) -> None:
    vm = TradingViewModel()

    assert vm.enabled is False
    assert vm.toggleBusy is False
    assert vm.symbol == ""
    assert vm.symbolOptions == []
    assert vm.ordersSentThisSession == 0
    assert vm.openSymbolsCount == 0


def test_set_symbol_options_updates_and_notifies(qapp) -> None:
    vm = TradingViewModel()
    seen = []
    vm.symbolOptionsChanged.connect(lambda: seen.append(vm.symbolOptions))

    vm.set_symbol_options(["BTCUSDT", "ETHUSDT"])

    assert vm.symbolOptions == ["BTCUSDT", "ETHUSDT"]
    assert seen == [["BTCUSDT", "ETHUSDT"]]


def test_symbol_property_only_emits_on_real_change(qapp) -> None:
    vm = TradingViewModel()
    vm.symbol = "BTCUSDT"
    count = 0
    vm.symbolChanged.connect(lambda: None)

    def _count():
        nonlocal count
        count += 1

    vm.symbolChanged.connect(_count)
    vm.symbol = "BTCUSDT"  # unchanged
    assert count == 0
    vm.symbol = "ETHUSDT"
    assert count == 1


def test_request_symbol_change_emits_only_for_a_real_new_symbol(qapp) -> None:
    vm = TradingViewModel()
    vm.symbol = "BTCUSDT"
    seen = []
    vm.symbolChangeRequested.connect(seen.append)

    vm.requestSymbolChange("BTCUSDT")
    assert seen == []

    vm.requestSymbolChange("ETHUSDT")
    assert seen == ["ETHUSDT"]

    vm.requestSymbolChange("")
    assert seen == ["ETHUSDT"]


def test_request_toggle_emits_toggle_requested(qapp) -> None:
    vm = TradingViewModel()
    seen = []
    vm.toggleRequested.connect(lambda: seen.append(True))

    vm.requestToggle()

    assert seen == [True]


def test_set_trading_state_updates_both_fields_together(qapp) -> None:
    vm = TradingViewModel()

    vm.set_trading_state(True, False)

    assert vm.enabled is True
    assert vm.toggleBusy is False


def test_set_status_updates_message_and_error_flag(qapp) -> None:
    vm = TradingViewModel()

    vm.set_status("Đã bật giao dịch.", False)

    assert vm.statusMessage == "Đã bật giao dịch."
    assert vm.statusIsError is False


def test_set_session_stats_updates_both_counters(qapp) -> None:
    vm = TradingViewModel()

    vm.set_session_stats(5, 2)

    assert vm.ordersSentThisSession == 5
    assert vm.openSymbolsCount == 2


def test_log_model_is_stable_across_reads(qapp) -> None:
    vm = TradingViewModel()

    assert vm.log_model is vm.log_model
    assert vm.logModel is vm.log_model
