"""`EPIC-028H` — the order panel's state: what was typed, parsed; the slider
tied to the maximum; and a new symbol forgetting the old one's inputs."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import FunctionType

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.amount_text import (
    parse_amount,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter_writer import (
    OrderEntryPresenterWriter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_user_intents import (
    OrderEntryUserIntents,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .order_entry_fixtures import SYMBOL, spot_context

_PUBLIC_METHOD_LIMIT = 15
_BUY = EntrySide.BUY
_SELL = EntrySide.SELL


def _loaded() -> OrderEntryViewModel:
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    vm.presenter_side().begin_symbol(SYMBOL)
    vm.presenter_side().set_context(spot_context())
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
        vm.intents.set_order_type(OrderType.STOP_MARKET)


def test_no_figures_before_the_terms_are_read() -> None:
    vm = OrderEntryViewModel(desk_profile_for(TradingVenue.SPOT_TESTNET))
    vm.presenter_side().begin_symbol(SYMBOL)

    assert vm.figures(_BUY) is None
    assert vm.message == f"Loading {SYMBOL}..."


def test_each_side_keeps_its_own_inputs() -> None:
    vm = _loaded()

    vm.intents.set_price(_BUY, "100")
    vm.intents.set_quantity(_BUY, "0.2")
    vm.intents.set_price(_SELL, "120")

    assert vm.entry(_BUY).price == 100
    assert vm.entry(_BUY).quantity == Decimal("0.2")
    assert vm.entry(_SELL).price == 120
    assert vm.entry(_SELL).quantity is None


def test_the_slider_sets_a_share_of_the_maximum_on_the_step() -> None:
    vm = _loaded()
    vm.intents.set_price(_SELL, "100")

    vm.intents.set_percent(_SELL, 50)

    assert vm.entry(_SELL).quantity == Decimal("0.25")
    assert vm.percent(_SELL) == 50


def test_the_slider_does_nothing_while_the_maximum_is_unknown() -> None:
    vm = _loaded()

    vm.intents.set_percent(_BUY, 50)  # no price, so no maximum

    assert vm.entry(_BUY).quantity is None


def test_the_last_price_fills_the_price_only_once_known() -> None:
    vm = _loaded()
    vm.intents.use_last_price(_BUY)
    assert vm.entry(_BUY).price is None

    vm.presenter_side().set_last_price(Decimal("101.5"))
    vm.intents.use_last_price(_BUY)

    assert vm.entry(_BUY).price == Decimal("101.5")


def test_a_new_symbol_forgets_the_old_one() -> None:
    vm = _loaded()
    vm.presenter_side().set_last_price(Decimal(100))
    vm.intents.set_price(_BUY, "100")

    vm.presenter_side().begin_symbol("ETHUSDT")

    assert vm.order_symbol == "ETHUSDT"
    assert vm.context is None
    assert vm.last_price is None
    assert vm.entry(_BUY).price is None


def test_an_edit_that_changes_nothing_is_not_announced() -> None:
    vm = _loaded()
    vm.intents.set_price(_BUY, "100")
    announced: list[None] = []
    vm.changed.connect(lambda: announced.append(None))

    vm.intents.set_price(_BUY, "100.0")
    vm.intents.set_order_type(OrderType.LIMIT)
    vm.presenter_side().set_last_price(None)

    assert announced == []


def test_submit_names_the_side() -> None:
    vm = _loaded()
    requested: list[str] = []
    vm.submitRequested.connect(requested.append)

    vm.intents.request_submit(_SELL)

    assert requested == ["SELL"]


# -- EPIC-028O -------------------------------------------------------------- #


def test_a_stop_price_and_a_total_are_kept_per_side() -> None:
    vm = _loaded()

    vm.intents.set_stop_price(_BUY, "105")
    vm.intents.set_total(_BUY, "250.5")
    vm.intents.set_stop_price(_SELL, "abc")

    assert vm.entry(_BUY).stop_price == 105
    assert vm.entry(_BUY).total == Decimal("250.5")
    assert vm.entry(_SELL).stop_price is None


def test_on_a_quote_sized_buy_the_slider_moves_the_total() -> None:
    vm = _loaded()
    vm.intents.set_order_type(OrderType.MARKET)
    vm.presenter_side().set_last_price(Decimal(300))

    vm.intents.set_percent(_BUY, 33)

    # 33 % of the 1000 USDT available, floored to a cent; no quantity typed.
    assert vm.entry(_BUY).total == Decimal("330.00")
    assert vm.entry(_BUY).quantity is None
    assert vm.percent(_BUY) == 33


def test_a_typed_total_moves_the_slider() -> None:
    vm = _loaded()
    vm.intents.set_order_type(OrderType.MARKET)
    vm.presenter_side().set_last_price(Decimal(300))

    vm.intents.set_total(_BUY, "250")

    assert vm.percent(_BUY) == 25


def test_the_total_slider_does_nothing_while_the_balance_is_unknown() -> None:
    vm = _loaded()
    vm.presenter_side().set_context(spot_context(available_quote=None))
    vm.intents.set_order_type(OrderType.MARKET)
    vm.presenter_side().set_last_price(Decimal(300))

    vm.intents.set_percent(_BUY, 50)

    assert vm.entry(_BUY).total is None


def test_the_best_price_button_asks_for_the_side_and_takes_the_answer() -> None:
    vm = _loaded()
    requested: list[str] = []
    vm.bestPriceRequested.connect(requested.append)

    vm.intents.use_best_price(_SELL)
    vm.presenter_side().set_price_value(_SELL, Decimal("101.25"))

    assert requested == ["SELL"]
    assert vm.entry(_SELL).price == Decimal("101.25")


def test_clearing_after_a_fill_clears_the_amount_and_the_total() -> None:
    vm = _loaded()
    vm.intents.set_price(_BUY, "100")
    vm.intents.set_quantity(_BUY, "1")
    vm.intents.set_total(_BUY, "50")

    vm.presenter_side().clear_amount(_BUY)

    assert vm.entry(_BUY).quantity is None
    assert vm.entry(_BUY).total is None
    assert vm.entry(_BUY).price == 100


def test_a_user_intent_announces_itself_on_the_view_models_signals() -> None:
    """`BOT-152`: the intents live apart from the signals, so a split that
    drops a connection leaves the view or the presenter deaf."""
    vm = _loaded()
    announced: list[None] = []
    focused: list[None] = []
    vm.changed.connect(lambda: announced.append(None))
    vm.focusRequested.connect(lambda: focused.append(None))

    vm.intents.set_price(_BUY, "100")
    vm.intents.set_order_type(OrderType.MARKET)
    vm.intents.request_focus()

    assert len(announced) == 2
    assert len(focused) == 1


def test_a_presenter_write_and_an_options_change_announce_on_changed() -> None:
    vm = _loaded()
    announced: list[None] = []
    vm.changed.connect(lambda: announced.append(None))

    vm.presenter_side().show_result("Placed.", is_error=False)
    vm.presenter_side().set_last_price(Decimal(100))
    vm.options.set_tp_sl_enabled(True)

    assert len(announced) == 3
    assert (vm.message, vm.last_price) == ("Placed.", Decimal(100))


def test_the_three_halves_each_stay_under_the_public_method_threshold() -> None:
    """`architecture-rule.md` §5.4: over 15 public methods forces a split."""
    for cls in (OrderEntryViewModel, OrderEntryUserIntents, OrderEntryPresenterWriter):
        public = [
            name
            for name, member in vars(cls).items()
            if not name.startswith("_") and isinstance(member, FunctionType | property)
        ]
        assert len(public) <= _PUBLIC_METHOD_LIMIT, (cls.__name__, public)


#: The files under `ui/desk` that may ask for the presenter's writes: the
#: definition, the presenters and their helpers, and the previews that load a
#: panel by hand. A new file asking for them fails the test below until a
#: person decides it is a presenter side.
_MAY_ASK_FOR_PRESENTER_SIDE = frozenset(
    {
        "desk_screen/preview.py",
        "order_entry/best_price_filler.py",
        "order_entry/futures_settings_changer.py",
        "order_entry/order_entry_presenter.py",
        "order_entry/order_entry_presenter_writer.py",
        "order_entry/order_entry_view_model.py",
        "order_entry/preview.py",
    }
)


def test_only_the_presenter_side_asks_for_the_presenters_writes() -> None:
    """The writes are held by presenters and their helpers; any other file
    under `ui/desk`, a view included, that asks for them fails here."""
    desk = Path(__file__).parents[6] / "src/modules/trading/ui/desk"
    asking = {
        path.relative_to(desk).as_posix()
        for path in desk.rglob("*.py")
        if "presenter_side" in path.read_text(encoding="utf-8")
    }
    assert asking == _MAY_ASK_FOR_PRESENTER_SIDE
    assert not hasattr(OrderEntryViewModel, "begin_symbol")


def test_submit_and_best_price_intents_reach_the_view_models_signals() -> None:
    """The presenter connects `submitRequested` and `bestPriceRequested` on the
    view model; the intents must emit them there."""
    vm = _loaded()
    submitted: list[str] = []
    best: list[str] = []
    vm.submitRequested.connect(submitted.append)
    vm.bestPriceRequested.connect(best.append)

    vm.intents.request_submit(_BUY)
    vm.intents.use_best_price(_SELL)

    assert (submitted, best) == (["BUY"], ["SELL"])
