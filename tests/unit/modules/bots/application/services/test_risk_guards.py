"""`EPIC-039F` - every venue profile answers the risk guard port, and Spot's answers nothing.

@details Spot's verdict lists are unchanged because its guard contributes none and
`GRID_CONSTRAINTS` gained no row (the Spot journeys' expected lists are the fixture)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk_guard_futures import (
    FuturesRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk_guard_spot import (
    SpotRiskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

_NOW = datetime(2026, 10, 13, tzinfo=UTC)


def _inputs(leverage: int) -> PlanRiskInputs:
    params = GridParams.from_config(
        {**CONFIG, "direction": "LONG", "leverage": str(leverage)}
    )
    return PlanRiskInputs(
        params,
        plan(params, TERMS, LAST_PRICE, LevelSizing.EQUAL_QUANTITY),
        FuturesSymbolSetting("BTCUSDT", leverage, MarginType.ISOLATED, Decimal(10**9)),
        LeverageBrackets(
            "BTCUSDT",
            (
                LeverageBracket(
                    1, 125, Decimal(0), Decimal(10**7), Decimal("0.004"), Decimal(0)
                ),
            ),
        ),
        LAST_PRICE,
        FuturesGridThresholds(),
    )


def test_spot_verdicts_are_unchanged_the_spot_guard_adds_none() -> None:
    assert SpotRiskGuard().judge_plan(_inputs(25)) == ()


def test_spots_run_time_state_is_safe_and_says_why() -> None:
    state = SpotRiskGuard().watch(
        RiskSnapshot(Decimal(1), Decimal(100), Decimal(99), _NOW), _NOW, RiskLevel.WARN
    )

    assert state.level is RiskLevel.SAFE
    assert "no liquidation" in state.reason


def test_the_futures_guard_judges_a_plan_and_a_snapshot() -> None:
    guard = FuturesRiskGuard(FuturesGridThresholds())

    verdicts = guard.judge_plan(_inputs(25))
    state = guard.watch(
        RiskSnapshot(Decimal(1), Decimal(100), Decimal(99), _NOW), _NOW, RiskLevel.SAFE
    )

    assert any(v.refuses for v in verdicts)
    assert state.level is RiskLevel.CRITICAL
