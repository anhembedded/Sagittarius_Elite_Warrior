"""EPIC-027B — `BrokerSimulationConfig.market_type` (ADR
`DECISION_2026-09-26_spot_market_axis.md` D1, D3)."""

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)


def test_market_type_defaults_to_usd_m_futures_so_existing_runs_are_unchanged():
    assert BrokerSimulationConfig().market_type is MarketType.FUTURES_USD_M


def test_spot_accepts_one_times_leverage_on_both_sides():
    config = BrokerSimulationConfig(market_type=MarketType.SPOT)

    assert config.market_type is MarketType.SPOT
    assert config.long_leverage == 1.0
    assert config.short_leverage == 1.0


@pytest.mark.parametrize(
    ("long_leverage", "short_leverage"),
    [(2.0, 1.0), (1.0, 2.0), (0.5, 1.0), (1.0001, 1.0)],
)
def test_spot_refuses_any_leverage_other_than_one(
    long_leverage: float, short_leverage: float
):
    with pytest.raises(ValueError, match="spot.*leverage"):
        BrokerSimulationConfig(
            market_type=MarketType.SPOT,
            long_leverage=long_leverage,
            short_leverage=short_leverage,
        )


def test_usd_m_futures_still_accepts_leverage():
    config = BrokerSimulationConfig(
        market_type=MarketType.FUTURES_USD_M, long_leverage=5.0, short_leverage=3.0
    )

    assert config.long_leverage == 5.0
    assert config.short_leverage == 3.0


def test_coin_m_futures_is_refused_as_unsupported():
    with pytest.raises(ValueError, match="futures_coin_m.*not supported"):
        BrokerSimulationConfig(market_type=MarketType.FUTURES_COIN_M)
