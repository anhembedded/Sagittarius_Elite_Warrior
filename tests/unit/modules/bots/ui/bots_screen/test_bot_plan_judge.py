"""`EPIC-029F` — the screen shows the kind's own judgement of a plan."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_judge import (
    NOT_READ_YET,
    judge,
    verdict_line,
)

from .bots_screen_fixtures import GOOD_CONFIG, REFUSED_CONFIG

_KIND = GridKind(executor_factory=None, thresholds=GridThresholds())  # type: ignore[arg-type]
_TERMS = ExchangeTerms(
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.00001"),
    min_notional=Decimal(5),
    maker_fee=Decimal("0.001"),
    taker_fee=Decimal("0.001"),
    max_notional_per_order=Decimal(5000),
    max_open_orders=100,
)
_MARKET = PlannerMarket(_TERMS, MarketView(Decimal(65000), Decimal(2500)), None, None)


def test_no_market_numbers_yet_means_no_start_and_no_overlay() -> None:
    judged = judge(_KIND, GOOD_CONFIG, None)

    assert (judged.refusal, judged.verdicts, judged.overlay) == (NOT_READ_YET, (), None)


def test_a_market_that_could_not_be_read_names_its_problem() -> None:
    unread = PlannerMarket(None, None, None, None, "spot_testnet is not enabled")

    assert judge(_KIND, GOOD_CONFIG, unread).refusal == (
        "The plan cannot be judged: spot_testnet is not enabled"
    )


def test_a_good_plan_may_start_and_draws_its_levels() -> None:
    judged = judge(_KIND, GOOD_CONFIG, _MARKET)

    assert judged.refusal == ""
    assert judged.overlay is not None and judged.overlay.lines
    assert not any(verdict.refuses for verdict in judged.verdicts)


def test_a_refused_plan_names_the_refusing_check() -> None:
    judged = judge(_KIND, REFUSED_CONFIG, _MARKET)

    refused = [verdict for verdict in judged.verdicts if verdict.refuses]
    assert refused
    assert judged.refusal == f"Refused: {refused[0].reason}"


def test_a_verdict_line_names_its_severity_and_its_numbers() -> None:
    verdict = Verdict(
        VerdictSeverity.WARNING,
        "RANGE_NARROW",
        "The range is narrow",
        {"measured_range": Decimal("10000.00"), "threshold": Decimal("1.140E+4")},
    )

    assert verdict_line(verdict) == (
        "Warning: The range is narrow (measured range 10,000, threshold 11,400)"
    )
    assert verdict_line(Verdict(VerdictSeverity.OK, "X", "Fine")) == "OK: Fine"
