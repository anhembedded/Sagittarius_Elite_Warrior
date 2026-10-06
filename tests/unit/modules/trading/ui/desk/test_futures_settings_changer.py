"""`EPIC-028I` — a margin-mode or leverage answer for a symbol the panel has
left is not shown on the new symbol's panel, nor followed by a read of it
(the PR #307 review); the change is still finished, so the next one is
accepted.

@details The verified `FakeFuturesSettingsControl`, a real view model, and
a worker pool that holds each task until the test runs it."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_futures_settings_control import (
    FakeFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_settings_changer import (
    FuturesSettingsChanger,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .order_entry_fixtures import SYMBOL, HeldThreadManager


class _Changer:
    def __init__(self) -> None:
        self.vm = OrderEntryViewModel(desk_profile_for(TradingVenue.FUTURES_TESTNET))
        self.vm.presenter_side().begin_symbol(SYMBOL)
        self.control = FakeFuturesSettingsControl()
        self.threads = HeldThreadManager()
        self.reads: list[str] = []
        self.changer = FuturesSettingsChanger(
            self.vm,
            self.control,
            self.threads,
            lambda: self.reads.append(self.vm.order_symbol),
        )


def test_an_answer_names_its_symbol_and_reads_it_again(qapp) -> None:
    desk = _Changer()

    desk.vm.options.request_leverage(20)
    desk.threads.run(0)
    qapp.processEvents()

    assert desk.vm.message == f"Set leverage 20x on {SYMBOL}."
    assert desk.reads == [SYMBOL]


def test_an_answer_for_a_symbol_the_panel_left_is_not_shown(qapp) -> None:
    desk = _Changer()
    desk.vm.options.request_leverage(20)
    desk.vm.presenter_side().begin_symbol("ETHUSDT")

    desk.threads.run(0)
    qapp.processEvents()

    assert desk.control.leverage_changes == [(SYMBOL, 20)]
    assert "Set leverage" not in desk.vm.message
    assert desk.reads == []
    desk.vm.options.request_leverage(5)
    assert len(desk.threads.pending) == 2
