"""`EPIC-029` ADR D6 r2 — Emergency Stop sells a bot's coins under the bot's
tag, and only the surplus no bot holds untagged.

@details Built as `test_emergency_stop_spot.py` builds a Spot stop. The book
is installed the way registration installs it; the stop reads it before its
step 1 clears every book.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.emergency_stop_builders import (
    make_handler,
    quiet_raw_client,
    spot_status,
)

_SPOT = TradingVenue.SPOT_TESTNET


def _book(tag: str, quantity: str) -> OwnerBook:
    registration = OwnerBudgetRegistration(
        owner_id=f"bot-{tag}",
        tag=tag,
        symbol="BTCUSDT",
        run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
        budget=OwnerBudget(10, Decimal(1000), timedelta(0), 60, timedelta(minutes=1)),
    )
    return OwnerBook(registration, OwnerInventory(Decimal(quantity), Decimal(1)))


def _sells(
    baseline: str, held: str, books: dict[str, str]
) -> list[tuple[str | None, Decimal]]:
    """The stop's sells as (tag, quantity), for a user holding `baseline`
    BTC before enabling and `held` BTC now."""
    state = TradingSessionState()
    state.enable(set(), spot_baseline_holdings={"BTC": Decimal(baseline)})
    for tag, quantity in books.items():
        state.install_owner_book(
            tag, _book(tag, quantity), expected_switch_epoch=state.switch_epoch
        )
    raw_client = quiet_raw_client()
    raw_client.futures_create_order.return_value = {}
    holding = SpotHolding("BTC", Decimal(held), Decimal(0), Decimal("0.00000001"))
    handler = make_handler(
        session_state=state,
        raw_client=raw_client,
        trading_venue=_SPOT,
        account_reader=FakeTradingAccountReader(spot_status((holding,))),
    )

    result = handler.execute(EmergencyStopCommand(venue=_SPOT))

    assert result.positions_closed.succeeded is True
    assert state.owner_books.shares() == ()
    return [
        (tag_of(call.kwargs["newClientOrderId"]), Decimal(call.kwargs["quantity"]))
        for call in raw_client.futures_create_order.call_args_list
    ]


def test_a_bots_coins_are_sold_under_its_tag_and_the_users_are_untouched() -> None:
    """The user held 0.5 before enabling and still does; the bot bought
    0.2 this session. 0.7 is held: the 0.2 surplus goes out tagged, and the
    user's 0.5 stays."""
    assert _sells("0.5", "0.7", {"a3f9c1": "0.2"}) == [("a3f9c1", Decimal("0.2"))]


def test_only_the_surplus_beyond_every_bot_goes_out_untagged() -> None:
    """A manual buy of 0.1 this session sits beside two bots' 0.2 and
    0.15: each bot's share carries its tag, and 0.1 is untagged."""
    assert _sells("0.5", "0.95", {"a3f9c1": "0.2", "b00000": "0.15"}) == [
        ("a3f9c1", Decimal("0.2")),
        ("b00000", Decimal("0.15")),
        (None, Decimal("0.1")),
    ]


def test_a_surplus_smaller_than_the_bots_inventory_is_all_the_bots() -> None:
    """Some of the bot's coins were sold by hand: the stop sells what is
    left of the surplus, under the bot's tag, and nothing untagged."""
    assert _sells("0.5", "0.6", {"a3f9c1": "0.2"}) == [("a3f9c1", Decimal("0.1"))]


def test_with_no_bot_the_stop_sells_untagged_as_before() -> None:
    assert _sells("0.5", "0.8", {}) == [(None, Decimal("0.3"))]
