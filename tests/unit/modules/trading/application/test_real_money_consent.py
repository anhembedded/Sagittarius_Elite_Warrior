"""`EPIC-034` D3, D11 — the question that names real money is asked once per
mainnet venue per session, never on a testnet, and a "no" sends nothing."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.real_money_consent import (
    RealMoneyConsent,
    RealMoneyQuestion,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_MAINNETS = [TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET]
_TESTNETS = [TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET]


class _Answers:
    def __init__(self, *answers: bool) -> None:
        self._answers = list(answers)
        self.asked: list[RealMoneyQuestion] = []

    def __call__(self, question: RealMoneyQuestion) -> bool:
        self.asked.append(question)
        return self._answers.pop(0)


@pytest.mark.parametrize("venue", _TESTNETS)
def test_a_testnet_is_never_asked(venue: TradingVenue) -> None:
    answers = _Answers()

    assert RealMoneyConsent(answers).confirmed(venue, "start this bot") is True
    assert answers.asked == []


@pytest.mark.parametrize("venue", _MAINNETS)
def test_a_mainnet_venue_asks_once_and_remembers_the_yes(venue: TradingVenue) -> None:
    answers = _Answers(True)
    consent = RealMoneyConsent(answers)

    first = consent.confirmed(venue, "place an order")
    second = consent.confirmed(venue, "arm a strategy")

    assert (first, second) == (True, True)
    assert answers.asked == [RealMoneyQuestion(venue, "place an order")]


def test_each_mainnet_venue_is_asked_for_itself() -> None:
    answers = _Answers(True, True)
    consent = RealMoneyConsent(answers)

    consent.confirmed(TradingVenue.SPOT_MAINNET, "start this bot")
    consent.confirmed(TradingVenue.FUTURES_MAINNET, "place an order")

    assert [q.venue for q in answers.asked] == _MAINNETS[:1] + _MAINNETS[1:]


def test_a_no_is_not_remembered_and_the_next_action_asks_again() -> None:
    answers = _Answers(False, True)
    consent = RealMoneyConsent(answers)

    declined = consent.confirmed(TradingVenue.SPOT_MAINNET, "start this bot")
    agreed = consent.confirmed(TradingVenue.SPOT_MAINNET, "start this bot")

    assert (declined, agreed) == (False, True)
    assert len(answers.asked) == 2


def test_a_new_session_asks_again() -> None:
    first, second = _Answers(True), _Answers(True)

    RealMoneyConsent(first).confirmed(TradingVenue.SPOT_MAINNET, "place an order")
    RealMoneyConsent(second).confirmed(TradingVenue.SPOT_MAINNET, "place an order")

    assert (len(first.asked), len(second.asked)) == (1, 1)
