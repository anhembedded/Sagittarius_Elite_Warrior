"""`EPIC-033I` — the Trade mode in the composed app, with Futures Testnet and
Spot Testnet both enabled, against the fake Binance server.

@details Re-homed from the Spot desk's file (`EPIC-033P` stage 3, from the
Dev Board's F9 tests before it): the order path now starts from the Trade
mode with Spot chosen on its toolbar. An order typed after Trade → New
order… (F9) runs from the venue's own Buy button to the wire and back.

The mode is also measured here with both venues' pages built, which the
conformance suite's boot cannot do (it enables no venue): every check of
`test_workbench_conformance.py` at each window size, with each venue shown,
and a picture of each (`SEW_UI_SCREENSHOTS`, `pr-review` SKILL §5.1).

`create_app()` builds everything, including the venue registry, the real
dispatcher and the real handlers. Four boundaries are substituted, at
configuration:
- the network: `python-binance` points at `run_binance_fake_server()` and
  each venue's key pair comes from the environment;
- the chart's market data, through the same seeded fakes the rest of this
  directory uses;
- the "Place this order?" dialog, a recorded Yes;
- `python-binance`'s `get_loop()`, which hands each worker thread a new event
  loop and never closes it (`BUG-075`). Each module binds the name itself
  (`Client.__init__` reaches it through `base_client` and, via `WebsocketAPI`,
  `ws.reconnecting_websocket`), so every binding (`_GET_LOOP_BINDINGS`) returns
  one loop the fixture owns and closes; `test_no_event_loop_is_left_unclosed`
  fails if one comes back.

Only the "trading on" test seeds the session as enabled directly: the toggle
would also start the venue's user-data websocket, which the fake server does
not speak. The composed path from the toggle through
`EnableTradingCommandHandler` is proven at unit level only (`EPIC-028S` §3).
The unit tests over fakes are `tests/unit/modules/trading/ui/trade/` and
`tests/unit/modules/trading/ui/desk/`.
"""

from __future__ import annotations

import gc
import warnings
from collections.abc import Iterator
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.trade_mode_boot import (
    SPOT,
    Boot,
    FakeServerUrls,
    TradeDesk,
    new_order,
    trade_mode_running,
)

#: The fake Spot account's USDT (`fake_exchange/spot_account_state.py`).
_FAKE_USDT = Decimal(100000)
#: Far below the fake's last price for the desk's symbol, so a Limit buy rests
#: open; its notional sits inside the app's per-order limit (`app_config.json`).
_RESTING_PRICE = "30000"
_QUANTITY = "0.001"
_WAIT_MS = 10_000


@pytest.fixture
def trade_boot(request: pytest.FixtureRequest) -> Boot:
    return Boot.from_request(request)


@pytest.fixture
def spot_desk(trade_boot: Boot) -> Iterator[TradeDesk]:
    with trade_mode_running(trade_boot) as desk:
        yield desk


def _type_resting_limit_buy(desk: TradeDesk, qtbot) -> None:
    vm = desk.presenter.orders
    qtbot.waitUntil(lambda: vm.context is not None, timeout=_WAIT_MS)
    vm.set_order_type(OrderType.LIMIT)
    vm.set_price(EntrySide.BUY, _RESTING_PRICE)
    vm.set_quantity(EntrySide.BUY, _QUANTITY)


def _buy(desk: TradeDesk, qtbot) -> None:
    qtbot.mouseClick(
        desk.view.findChild(QPushButton, "btnSubmitBuy"), Qt.MouseButton.LeftButton
    )


def _order_posts(urls: FakeServerUrls) -> list[tuple[str, str]]:
    """Live order placements only: not `/order/test` (validate-only) nor
    `/orderList`."""
    return [r for r in urls.requests if r == ("POST", "/api/v3/order")]


def test_f9_focuses_the_spot_entry_read_from_the_venue(spot_desk, qtbot) -> None:
    vm = spot_desk.presenter.orders
    assert vm.profile.venue is SPOT
    qtbot.waitUntil(lambda: vm.context is not None, timeout=_WAIT_MS)
    spot_desk.view.activateWindow()

    new_order(spot_desk)

    price = spot_desk.view.findChild(QLineEdit, "txtPriceBuy")
    qtbot.waitUntil(lambda: QApplication.focusWidget() is price, timeout=_WAIT_MS)
    assert vm.context.available_quote == _FAKE_USDT
    assert _order_posts(spot_desk.urls) == []


def test_a_buy_while_trading_is_off_is_refused_in_words_and_never_sent(
    spot_desk, qtbot
) -> None:
    """The real handler's gate answers, and nothing reaches the exchange."""
    new_order(spot_desk)
    _type_resting_limit_buy(spot_desk, qtbot)
    vm = spot_desk.presenter.orders
    refusal = format_execute_order_block_reason(
        ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
    )

    _buy(spot_desk, qtbot)

    qtbot.waitUntil(lambda: refusal in vm.message, timeout=_WAIT_MS)
    assert vm.message_is_error
    assert _order_posts(spot_desk.urls) == []


def test_a_resting_limit_placed_on_the_desk_reaches_the_venue_and_open_orders(
    spot_desk, qtbot
) -> None:
    spot_desk.scopes.get(SPOT).session_state.enable(
        set(), spot_baseline_holdings={"USDT": _FAKE_USDT}
    )
    new_order(spot_desk)
    _type_resting_limit_buy(spot_desk, qtbot)

    _buy(spot_desk, qtbot)

    qtbot.waitUntil(lambda: len(_order_posts(spot_desk.urls)) == 1, timeout=_WAIT_MS)
    rows = spot_desk.view.account_tabs.open_orders_panel.table.model()
    qtbot.waitUntil(lambda: rows.rowCount() == 1, timeout=_WAIT_MS)
    cells = [rows.index(0, column).data() for column in range(rows.columnCount())]
    assert spot_desk.presenter.desk.symbol in cells
    assert "BUY" in cells
    assert "LIMIT" in cells
    assert "NEW" in cells  # resting on the exchange, not a validate-only echo


def test_no_event_loop_is_left_unclosed(trade_boot: Boot, qtbot) -> None:
    """The PR 310 review — `python-binance` gives each worker thread an event
    loop and never closes it (`BUG-075`). Patching one of its `get_loop`
    bindings left the leak in place; an orphaned loop is collected later and
    fails whichever test is running. Booting, reading the desk's order entry
    and shutting down leaves no unclosed loop behind."""
    gc.collect()  # what earlier tests left is not this file's
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        with trade_mode_running(trade_boot) as desk:
            new_order(desk)
            vm = desk.presenter.orders
            qtbot.waitUntil(lambda: vm.context is not None, timeout=_WAIT_MS)
        gc.collect()

    leaks = [w for w in caught if "unclosed event loop" in str(w.message)]
    assert leaks == []
