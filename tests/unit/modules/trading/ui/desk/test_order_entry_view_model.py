"""`EPIC-028H` — the order panel's state: what was typed, parsed; the slider
tied to the maximum; and a new symbol forgetting the old one's inputs."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
    parse_amount,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .order_entry_fixtures import SYMBOL, spot_context

_BUY = EntrySide.BUY
_SELL = EntrySide.SELL


def _loaded() -> OrderEntryViewModel:
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    vm.begin_symbol(SYMBOL)
    vm.set_context(spot_context())
    return vm


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.5", Decimal("1.5")),
        (" 1,234.5 ", Decimal("1234.5")),
        ("0", Decimal(0)),
        ("", None),
        ("abc", None),
        ("-1", None),
        ("NaN", None),
        ("Infinity", None),
    ],
)
def test_only_a_real_non_negative_amount_is_read(
    text: str, expected: Decimal | None
) -> None:
    assert parse_amount(text) == expected


def test_the_first_offered_order_type_is_chosen_and_others_are_refused() -> None:
    vm = _loaded()

    assert vm.order_type is OrderType.LIMIT
    with pytest.raises(ValueError, match="not offered"):
        vm.set_order_type(OrderType.STOP_MARKET)


def test_no_figures_before_the_terms_are_read() -> None:
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    vm.begin_symbol(SYMBOL)

    assert vm.figures(_BUY) is None
    assert vm.message == f"Loading {SYMBOL}..."


def test_each_side_keeps_its_own_inputs() -> None:
    vm = _loaded()

    vm.set_price(_BUY, "100")
    vm.set_quantity(_BUY, "0.2")
    vm.set_price(_SELL, "120")

    assert vm.entry(_BUY).price == 100
    assert vm.entry(_BUY).quantity == Decimal("0.2")
    assert vm.entry(_SELL).price == 120
    assert vm.entry(_SELL).quantity is None


def test_the_slider_sets_a_share_of_the_maximum_on_the_step() -> None:
    vm = _loaded()
    vm.set_price(_SELL, "100")

    vm.set_percent(_SELL, 50)

    assert vm.entry(_SELL).quantity == Decimal("0.25")
    assert vm.percent(_SELL) == 50


def test_the_slider_does_nothing_while_the_maximum_is_unknown() -> None:
    vm = _loaded()

    vm.set_percent(_BUY, 50)  # no price, so no maximum

    assert vm.entry(_BUY).quantity is None


def test_the_last_price_fills_the_price_only_once_known() -> None:
    vm = _loaded()
    vm.use_last_price(_BUY)
    assert vm.entry(_BUY).price is None

    vm.set_last_price(Decimal("101.5"))
    vm.use_last_price(_BUY)

    assert vm.entry(_BUY).price == Decimal("101.5")


def test_a_new_symbol_forgets_the_old_one() -> None:
    vm = _loaded()
    vm.set_last_price(Decimal(100))
    vm.set_price(_BUY, "100")

    vm.begin_symbol("ETHUSDT")

    assert vm.order_symbol == "ETHUSDT"
    assert vm.context is None
    assert vm.last_price is None
    assert vm.entry(_BUY).price is None


def test_an_edit_that_changes_nothing_is_not_announced() -> None:
    vm = _loaded()
    vm.set_price(_BUY, "100")
    announced: list[None] = []
    vm.changed.connect(lambda: announced.append(None))

    vm.set_price(_BUY, "100.0")
    vm.set_order_type(OrderType.LIMIT)
    vm.set_last_price(None)

    assert announced == []


def test_submit_names_the_side() -> None:
    vm = _loaded()
    requested: list[str] = []
    vm.submitRequested.connect(requested.append)

    vm.request_submit(_SELL)

    assert requested == ["SELL"]


# -- EPIC-028O -------------------------------------------------------------- #


def test_a_stop_price_and_a_total_are_kept_per_side() -> None:
    vm = _loaded()

    vm.set_stop_price(_BUY, "105")
    vm.set_total(_BUY, "250.5")
    vm.set_stop_price(_SELL, "abc")

    assert vm.entry(_BUY).stop_price == 105
    assert vm.entry(_BUY).total == Decimal("250.5")
    assert vm.entry(_SELL).stop_price is None


def test_on_a_quote_sized_buy_the_slider_moves_the_total() -> None:
    vm = _loaded()
    vm.set_order_type(OrderType.MARKET)
    vm.set_last_price(Decimal(300))

    vm.set_percent(_BUY, 33)

    # 33 % of the 1000 USDT available, floored to a cent; no quantity typed.
    assert vm.entry(_BUY).total == Decimal("330.00")
    assert vm.entry(_BUY).quantity is None
    assert vm.percent(_BUY) == 33


def test_a_typed_total_moves_the_slider() -> None:
    vm = _loaded()
    vm.set_order_type(OrderType.MARKET)
    vm.set_last_price(Decimal(300))

    vm.set_total(_BUY, "250")

    assert vm.percent(_BUY) == 25


def test_the_total_slider_does_nothing_while_the_balance_is_unknown() -> None:
    vm = _loaded()
    vm.set_context(spot_context(available_quote=None))
    vm.set_order_type(OrderType.MARKET)
    vm.set_last_price(Decimal(300))

    vm.set_percent(_BUY, 50)

    assert vm.entry(_BUY).total is None


def test_the_best_price_button_asks_for_the_side_and_takes_the_answer() -> None:
    vm = _loaded()
    requested: list[str] = []
    vm.bestPriceRequested.connect(requested.append)

    vm.use_best_price(_SELL)
    vm.set_price_value(_SELL, Decimal("101.25"))

    assert requested == ["SELL"]
    assert vm.entry(_SELL).price == Decimal("101.25")


def test_clearing_after_a_fill_clears_the_amount_and_the_total() -> None:
    vm = _loaded()
    vm.set_price(_BUY, "100")
    vm.set_quantity(_BUY, "1")
    vm.set_total(_BUY, "50")

    vm.clear_amount(_BUY)

    assert vm.entry(_BUY).quantity is None
    assert vm.entry(_BUY).total is None
    assert vm.entry(_BUY).price == 100
