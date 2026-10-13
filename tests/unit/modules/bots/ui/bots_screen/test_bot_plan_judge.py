"""`EPIC-029F` — the screen shows the kind's own judgement of a plan."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    ExchangeTerms,
    MarketView,
    PlanRiskFacts,
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
    PlanWorld,
    judge,
    verdict_line,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
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


def test_no_market_numbers_yet_means_no_verdicts_and_no_overlay() -> None:
    """What Start waits on is the readiness's to say (`EPIC-034H`); the judge
    only has nothing to show."""
    judged = judge(_KIND, GOOD_CONFIG, None)

    assert (judged.verdicts, judged.overlay) == ((), None)


def test_a_market_that_could_not_be_read_has_nothing_to_judge() -> None:
    unread = PlannerMarket(None, None, None, None, "spot_testnet is not enabled")

    judged = judge(_KIND, GOOD_CONFIG, unread)

    assert (judged.verdicts, judged.overlay) == ((), None)


def test_a_good_plan_draws_its_levels_and_nothing_refuses() -> None:
    judged = judge(_KIND, GOOD_CONFIG, _MARKET)

    assert judged.overlay is not None and judged.overlay.lines
    assert not any(verdict.refuses for verdict in judged.verdicts)


def test_a_refused_plan_has_its_refusing_check_among_the_verdicts() -> None:
    judged = judge(_KIND, REFUSED_CONFIG, _MARKET)

    assert [v.code for v in judged.verdicts if v.refuses] == [
        "LEVEL_BELOW_MIN_NOTIONAL"
    ]


def test_the_account_is_judged_beside_the_plan() -> None:
    cannot_trade = AccountView(Decimal(1), "USDT", False, "Spot Testnet")

    judged = judge(_KIND, GOOD_CONFIG, _MARKET, PlanWorld(cannot_trade))

    refusing = [v.code for v in judged.verdicts if v.refuses]
    assert refusing == ["KEY_CANNOT_TRADE"]
    # The balance is the exchange snapshot's to judge (`BOT-174`): a poor
    # account is not a verdict of the plan.
    assert "CAPITAL_ABOVE_BALANCE" not in [v.code for v in judged.verdicts]


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


def test_a_position_venues_plan_is_judged_for_liquidation_in_the_same_list() -> None:
    """`EPIC-039J` — the Futures verdicts come through the kind and reach the same list of
    lines a Spot plan's do, each with its code's words and its numbers."""
    facts = PlanRiskFacts(
        FuturesSymbolSetting("BTCUSDT", 3, MarginType.ISOLATED, Decimal(10**9)),
        LeverageBrackets(
            "BTCUSDT",
            (
                LeverageBracket(
                    1, 125, Decimal(0), Decimal(10**7), Decimal("0.004"), Decimal(0)
                ),
            ),
        ),
    )
    exposure = PlanWorld(
        limits=ExposureLimits(frozenset(TradeDirection), 20), risk=facts
    )
    config = {
        **GOOD_CONFIG,
        "direction": "LONG",
        "leverage": "3",
        "stop_loss": "percent:5",
    }

    judged = judge(_KIND, config, _MARKET, exposure)

    estimate = next(v for v in judged.verdicts if v.code == "LIQUIDATION_ESTIMATE")
    assert estimate.subject == "long"
    line = verdict_line(estimate)
    assert line.startswith("OK: Estimated liquidation price of the long")
    assert "an estimate, not a guarantee" in line
    assert "liquidation price" in line.split("(")[-1]


def test_the_same_plan_on_a_venue_with_no_word_is_refused_for_its_leverage() -> None:
    """Without the venue's limits a leveraged plan is the Spot profile's to judge: refused,
    never silently accepted."""
    config = {**GOOD_CONFIG, "direction": "LONG", "leverage": "3"}

    judged = judge(_KIND, config, _MARKET)

    assert any(v.refuses for v in judged.verdicts)
    assert not any(v.code == "LIQUIDATION_ESTIMATE" for v in judged.verdicts)
