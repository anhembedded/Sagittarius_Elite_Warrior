"""`EPIC-039G` — a Futures plan is judged on the account's fees and on funding.

The fees come from the account, not from a constant: the break-even step is twice the
account's maker rate, and the cost model, the break-even check and the readiness numbers
all read that one figure. Funding is a cost a held position pays or earns; `None` is its
unknown, never a zero."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_exchange_terms import (
    exchange_terms_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.cost_model_futures import (
    FuturesCostModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.cost_model_spot import (
    SpotCostModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.funding_view import (
    funding_view_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    FundingView,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.funding_rate import (
    FundingRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
    FuturesReads,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    terms_entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)

_ALL_DIRECTIONS = ExposureLimits(frozenset(TradeDirection), 125)
_AT = datetime(2026, 10, 13, 8, tzinfo=UTC)


def _futures_terms(maker: str, taker: str) -> FakeOrderEntryTerms:
    entry = replace(
        terms_entry(), commission=CommissionRate(SYMBOL, Decimal(maker), Decimal(taker))
    )
    return FakeOrderEntryTerms(entry)


def _thin_step_inputs(terms: FakeOrderEntryTerms) -> BotKindInputs:
    """A 0.1 % step: it earns after a 0.02 % maker fee on both legs and loses after Spot's 0.1 %."""
    return BotKindInputs(
        {
            "lower": "100",
            "upper": "100.4",
            "grid_count": "4",
            "spacing": "ARITHMETIC",
            "capital_quote": "1000",
            "stop_loss": "off",
            "take_profit": "off",
        },
        exchange_terms_for(terms, SYMBOL, DEFAULT_OWNER_BUDGET_CAPS),
        MarketView(Decimal("100.2")),
    )


def _break_even(evaluation) -> object:
    return next(
        v
        for v in evaluation.verdicts
        if v.code in {"BREAK_EVEN", "EVERY_CYCLE_LOSES", "SOME_GRIDS_LOSE"}
    )


def test_futures_fees_come_from_the_account_and_set_the_break_even_step() -> None:
    futures = _thin_step_inputs(_futures_terms("0.0002", "0.0005"))
    model = FuturesCostModel(futures.terms, FundingView(Decimal("0.0001")))

    verdict = _break_even(evaluate_grid(futures, GridThresholds()))

    assert model.fees() == (Decimal("0.0002"), Decimal("0.0005"))
    assert model.breakeven_step_fraction() == Decimal("0.0004")
    assert verdict.severity is VerdictSeverity.OK
    assert verdict.numbers["two_maker_fees"] == model.breakeven_step_fraction()


def test_the_same_step_loses_on_a_higher_account_rate() -> None:
    """The fee is read, not assumed: Spot-like 0.1 % rates make this step lose every cycle."""
    inputs_ = _thin_step_inputs(_futures_terms("0.001", "0.001"))

    verdict = _break_even(evaluate_grid(inputs_, GridThresholds()))

    assert verdict.severity is VerdictSeverity.REFUSED


def test_spot_costs_are_its_two_fees_and_no_funding_by_definition() -> None:
    model = SpotCostModel(inputs().terms)

    assert model.fees() == (Decimal("0.001"), Decimal("0.001"))
    assert model.breakeven_step_fraction() == Decimal("0.002")
    assert model.funding_estimate(Decimal(1000), timedelta(hours=24)) == 0


def test_funding_is_the_rate_times_the_position_for_the_horizon() -> None:
    terms = _thin_step_inputs(_futures_terms("0.0002", "0.0005")).terms
    model = FuturesCostModel(terms, FundingView(Decimal("0.0001")))

    assert model.funding_estimate(Decimal(1000), timedelta(hours=8)) == Decimal("0.1")
    assert model.funding_estimate(Decimal(1000), timedelta(hours=24)) == Decimal("0.3")
    assert model.funding_estimate(Decimal(-1000), timedelta(hours=8)) == Decimal("-0.1")


def test_an_unreadable_funding_rate_is_unknown_not_zero() -> None:
    reads = _futures_terms("0.0002", "0.0005")  # no funding seeded: the read fails
    view = funding_view_of(reads, SYMBOL)
    assert view == FundingView(None)

    terms = _thin_step_inputs(reads).terms
    assert (
        FuturesCostModel(terms, view).funding_estimate(
            Decimal(1000), timedelta(hours=8)
        )
        is None
    )

    judged = evaluate_grid(
        replace(inputs(funding=view), limits=_ALL_DIRECTIONS), GridThresholds()
    )
    funding = next(v for v in judged.verdicts if v.code == "FUNDING_NOT_CHECKED")
    assert funding.severity is VerdictSeverity.OK


def test_a_venue_without_funding_is_no_funding_not_a_zero_rate() -> None:
    spot = FakeOrderEntryTerms(
        terms_entry(), futures=FuturesReads.not_applicable(SYMBOL)
    )

    assert funding_view_of(spot, SYMBOL) is None
    judged = evaluate_grid(inputs(), GridThresholds())
    assert (
        next(v for v in judged.verdicts if v.code == "NO_FUNDING").severity
        is VerdictSeverity.OK
    )


def test_the_funding_view_carries_the_rate_the_exchange_reports() -> None:
    reads = FakeOrderEntryTerms(
        terms_entry(),
        futures=FuturesReads(
            funding={SYMBOL: FundingRate(SYMBOL, Decimal("-0.0003"), _AT, _AT)}
        ),
    )

    assert funding_view_of(reads, SYMBOL) == FundingView(Decimal("-0.0003"))


def _judge_funding(rate: str, direction: str, **thresholds: Decimal):
    base = inputs(funding=FundingView(Decimal(rate)), direction=direction, leverage="1")
    judged = evaluate_grid(
        replace(base, limits=_ALL_DIRECTIONS),
        GridThresholds(futures=FuturesGridThresholds(**thresholds)),
    )
    return next(v for v in judged.verdicts if v.code.startswith("FUNDING"))


def test_funding_adverse_warns_when_it_eats_the_cycle_profit() -> None:
    verdict = _judge_funding("0.01", "LONG")

    assert (verdict.code, verdict.severity) == (
        "FUNDING_ADVERSE",
        VerdictSeverity.WARNING,
    )
    assert verdict.numbers["cost_per_interval"] > 0


def test_a_long_that_funding_pays_is_not_warned() -> None:
    verdict = _judge_funding("-0.01", "LONG")

    assert (verdict.code, verdict.severity) == ("FUNDING", VerdictSeverity.OK)


def test_a_short_pays_the_negative_rate_and_earns_the_positive_one() -> None:
    assert _judge_funding("-0.01", "SHORT").code == "FUNDING_ADVERSE"
    assert _judge_funding("0.01", "SHORT").code == "FUNDING"


def test_a_neutral_ladder_opens_no_position_so_funding_does_not_warn() -> None:
    assert _judge_funding("0.05", "NEUTRAL").code == "FUNDING"


def test_the_share_is_a_threshold_not_a_literal() -> None:
    """A small rate is fine at the default 25 %; a stricter share warns on the same plan."""
    assert _judge_funding("0.0005", "LONG").code == "FUNDING"
    stricter = _judge_funding("0.0005", "LONG", funding_adverse_share=Decimal("0.0001"))
    assert stricter.code == "FUNDING_ADVERSE"


@pytest.mark.parametrize("rate", ["0", "0.0000"])
def test_a_rate_of_exactly_zero_costs_nothing(rate: str) -> None:
    assert _judge_funding(rate, "LONG").code == "FUNDING"
