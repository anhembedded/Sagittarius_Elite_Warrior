from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view_model import (
    DeskViewModel,
)


def test_starts_on_no_symbol_and_no_options(qapp) -> None:
    vm = DeskViewModel()

    assert vm.current_symbol == ""
    assert vm.symbolOptions == []


def test_set_symbol_options_updates_and_notifies(qapp) -> None:
    vm = DeskViewModel()
    seen = []
    vm.symbolOptionsChanged.connect(lambda: seen.append(vm.symbolOptions))

    vm.set_symbol_options(["BTCUSDT", "ETHUSDT"])

    assert vm.symbolOptions == ["BTCUSDT", "ETHUSDT"]
    assert seen == [["BTCUSDT", "ETHUSDT"]]


def test_symbol_property_only_emits_on_real_change(qapp) -> None:
    vm = DeskViewModel()
    vm.set_symbol("BTCUSDT")
    count = 0
    vm.symbolChanged.connect(lambda: None)

    def _count():
        nonlocal count
        count += 1

    vm.symbolChanged.connect(_count)
    vm.set_symbol("BTCUSDT")  # unchanged
    assert count == 0
    vm.set_symbol("ETHUSDT")
    assert count == 1


def test_request_symbol_change_emits_only_for_a_real_new_symbol(qapp) -> None:
    vm = DeskViewModel()
    vm.set_symbol("BTCUSDT")
    seen = []
    vm.symbolChangeRequested.connect(seen.append)

    vm.requestSymbolChange("BTCUSDT")
    assert seen == []

    vm.requestSymbolChange("ETHUSDT")
    assert seen == ["ETHUSDT"]

    vm.requestSymbolChange("")
    assert seen == ["ETHUSDT"]


def test_request_emergency_stop_emits_emergency_stop_requested(qapp) -> None:
    vm = DeskViewModel()
    seen = []
    vm.emergencyStopRequested.connect(lambda: seen.append(True))

    vm.requestEmergencyStop()

    assert seen == [True]


def test_set_status_updates_message_and_error_flag(qapp) -> None:
    vm = DeskViewModel()

    vm.set_status("Emergency stop completed.", False)

    assert vm.statusMessage == "Emergency stop completed."
    assert vm.statusIsError is False


def test_log_model_is_stable_across_reads(qapp) -> None:
    vm = DeskViewModel()

    assert vm.log_model is vm.log_model
    assert vm.logModel is vm.log_model
