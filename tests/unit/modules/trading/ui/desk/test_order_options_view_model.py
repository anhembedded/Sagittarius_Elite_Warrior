"""`EPIC-028I` — the panel's order options fold into a side's input only as
far as they change its figures: reduce-only on both sides, TP/SL levels only
while TP/SL is on; a re-read keeps what the panel last said."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    SideInput,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_options_view_model import (
    OrderOptionsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .order_entry_fixtures import SYMBOL, spot_context

_BUY = EntrySide.BUY
_SELL = EntrySide.SELL


def test_reduce_only_applies_to_both_sides() -> None:
    options = OrderOptionsViewModel()
    options.set_reduce_only(True)

    assert options.apply_to(_BUY, SideInput()).reduce_only
    assert options.apply_to(_SELL, SideInput()).reduce_only


def test_levels_count_only_while_tp_sl_is_on_and_only_for_their_side() -> None:
    options = OrderOptionsViewModel()
    options.set_take_profit(_BUY, "63000")
    options.set_stop_loss(_BUY, "58000")

    assert options.protection(_BUY) is None
    assert options.apply_to(_BUY, SideInput()).take_profit is None

    options.set_tp_sl_enabled(True)

    assert options.protection(_BUY) == ProtectiveLevels(Decimal(63000), Decimal(58000))
    assert options.apply_to(_BUY, SideInput()).stop_loss == Decimal(58000)
    assert options.protection(_SELL) is None


def test_a_zero_or_unreadable_level_is_no_level() -> None:
    options = OrderOptionsViewModel()
    options.set_tp_sl_enabled(True)
    options.set_take_profit(_BUY, "0")
    options.set_stop_loss(_BUY, "abc")

    assert options.protection(_BUY) is None


def test_the_chips_ask_rather_than_set() -> None:
    options = OrderOptionsViewModel()
    margins: list[object] = []
    leverages: list[int] = []
    options.marginTypeRequested.connect(margins.append)
    options.leverageRequested.connect(leverages.append)

    options.request_margin_type(MarginType.ISOLATED)
    options.request_leverage(25)

    assert margins == [MarginType.ISOLATED]
    assert leverages == [25]
    assert options.setting is None


def test_a_new_symbol_forgets_the_levels_typed_for_the_last() -> None:
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.FUTURES_TESTNET))
    vm.options.set_tp_sl_enabled(True)
    vm.options.set_take_profit(_BUY, "63000")

    vm.presenter_side().begin_symbol("ETHUSDT")

    assert vm.options.protection(_BUY) is None


def test_a_re_read_keeps_what_the_panel_last_said() -> None:
    """Only a new symbol's "Loading" line is cleared when its terms arrive;
    "Order placed" survives the re-read that follows the order."""
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    vm.presenter_side().begin_symbol(SYMBOL)
    vm.presenter_side().set_context(spot_context())
    assert vm.message == ""

    vm.presenter_side().show_result("Order placed (SEW-1).", is_error=False)
    vm.presenter_side().set_context(spot_context())

    assert vm.message == "Order placed (SEW-1)."
