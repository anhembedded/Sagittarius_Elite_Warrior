"""`EPIC-039L` (criterion 9) - what a halt that cannot close says about the protective stop."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.stop_words import (
    stop_words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_STOP = ProtectiveStop("SEW-a-0000000001", OrderSide.SELL, Decimal(90))


def test_a_stop_the_exchange_lists_stands() -> None:
    assert stop_words([_STOP], {_STOP.client_order_id}) == (
        "its protective stop stands on the exchange"
    )


def test_a_recorded_stop_the_exchange_does_not_list_is_not_claimed() -> None:
    assert stop_words([_STOP], set()) == "its protective stop is not on the exchange"


def test_a_bot_with_no_record_has_no_stop() -> None:
    assert stop_words([], set()) == "no protective stop stands over it"


def test_an_unread_exchange_is_said_to_be_unread_never_to_have_no_stop() -> None:
    assert stop_words([_STOP], None) == (
        "whether its protective stop stands could not be read"
    )
