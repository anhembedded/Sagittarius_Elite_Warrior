"""Unit tests for BacktestRunConfig and FSM State Matrix (BOT-095B, BOT-104)."""

from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BACKTEST_STATE_TRANSITIONS,
    BacktestRunConfig,
    BacktestUiEvent,
    BacktestUiState,
)


def _base_config() -> BacktestRunConfig:
    return BacktestRunConfig(
        strategy_key="ema_crossover",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=10_000.0,
        start_time=None,
        end_time=None,
    )


def test_fsm_state_transitions_basic_lifecycle():
    assert (
        BACKTEST_STATE_TRANSITIONS[
            (BacktestUiState.IDLE, BacktestUiEvent.RUN_REQUESTED)
        ]
        == BacktestUiState.RUNNING
    )
    assert (
        BACKTEST_STATE_TRANSITIONS[
            (BacktestUiState.RUNNING, BacktestUiEvent.BACKTEST_SUCCEEDED)
        ]
        == BacktestUiState.COMPLETED
    )
    assert (
        BACKTEST_STATE_TRANSITIONS[
            (BacktestUiState.COMPLETED, BacktestUiEvent.CONFIG_CHANGED)
        ]
        == BacktestUiState.CONFIG_DIRTY
    )


def test_compute_diff_summary_detects_position_sizing_changes():
    cfg1 = _base_config()
    cfg2 = BacktestRunConfig(
        strategy_key=cfg1.strategy_key,
        timeframe=cfg1.timeframe,
        initial_balance=cfg1.initial_balance,
        start_time=cfg1.start_time,
        end_time=cfg1.end_time,
        position_sizing=PositionSizing(
            type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0
        ),
    )

    diff = cfg1.compute_diff_summary(cfg2)
    assert "Kích thước lệnh (100.0% → 20.0%)" in diff


def test_compute_diff_summary_detects_broker_simulation_changes():
    cfg1 = _base_config()
    cfg2 = BacktestRunConfig(
        strategy_key=cfg1.strategy_key,
        timeframe=cfg1.timeframe,
        initial_balance=cfg1.initial_balance,
        start_time=cfg1.start_time,
        end_time=cfg1.end_time,
        broker_config=BrokerSimulationConfig(
            pyramiding=3,
            slippage_ticks=5,
            commission_type=CommissionType.PERCENT,
            commission_value=0.05,
        ),
    )

    diff = cfg1.compute_diff_summary(cfg2)
    assert "Kim tự tháp (1 → 3)" in diff
    assert "Trượt giá (0 → 5 ticks)" in diff
    assert "Phí hoa hồng (0.1 → 0.05)" in diff
