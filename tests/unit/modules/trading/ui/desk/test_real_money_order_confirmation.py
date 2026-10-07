"""`EPIC-034` D3, D11 — a manual order on a mainnet venue is preceded, the first time
of the session, by the question that names real money; declining it declines the
order, and the order's own confirmation (its details) is asked only after a yes."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_real_money_consent import (
    FakeRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    with_real_money_consent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_MAINNETS = [TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET]
_TESTNETS = [TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET]


@pytest.mark.parametrize("venue", _MAINNETS)
def test_a_yes_to_real_money_then_the_orders_own_confirmation_decides(
    venue: TradingVenue,
) -> None:
    consent = FakeRealMoneyConsent(agrees=True)
    inner = Mock(return_value=True)
    confirmation = Mock()

    ask = with_real_money_consent(inner, consent, venue)

    assert ask(confirmation) is True
    assert consent.asked == [(venue, "place an order")]
    inner.assert_called_once_with(confirmation)


@pytest.mark.parametrize("venue", _MAINNETS)
def test_the_orders_own_no_still_declines_after_a_yes_to_real_money(
    venue: TradingVenue,
) -> None:
    ask = with_real_money_consent(
        Mock(return_value=False), FakeRealMoneyConsent(agrees=True), venue
    )

    assert ask(Mock()) is False


@pytest.mark.parametrize("venue", _MAINNETS)
def test_declining_real_money_declines_the_order_before_its_details_are_shown(
    venue: TradingVenue,
) -> None:
    inner = Mock(return_value=True)

    ask = with_real_money_consent(inner, FakeRealMoneyConsent(agrees=False), venue)

    assert ask(Mock()) is False
    inner.assert_not_called()


@pytest.mark.parametrize("venue", _TESTNETS)
def test_a_testnet_order_is_confirmed_as_before_with_no_question(
    venue: TradingVenue,
) -> None:
    consent = FakeRealMoneyConsent(agrees=False)
    inner = Mock(return_value=True)

    ask = with_real_money_consent(inner, consent, venue)

    assert ask(Mock()) is True
    assert consent.asked == []
