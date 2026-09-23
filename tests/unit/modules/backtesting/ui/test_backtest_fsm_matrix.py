"""Unit tests for BacktestRunConfig and FSM State Matrix (BOT-095B, BOT-104)."""

from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BACKTEST_STATE_TRANSITIONS,
    BacktestExecutionMode,
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
    assert "Order size (100.0% → 20.0%)" in diff


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
    assert "Pyramiding (1 → 3)" in diff
    assert "Slippage (0 → 5 ticks)" in diff
    assert "Commission (0.1 → 0.05)" in diff


def test_compute_diff_summary_detects_leverage_changes():
    cfg1 = _base_config()
    cfg2 = BacktestRunConfig(
        strategy_key=cfg1.strategy_key,
        timeframe=cfg1.timeframe,
        initial_balance=cfg1.initial_balance,
        start_time=cfg1.start_time,
        end_time=cfg1.end_time,
        broker_config=BrokerSimulationConfig(long_leverage=5.0, short_leverage=3.0),
    )

    diff = cfg1.compute_diff_summary(cfg2)
    assert "Leverage (Long 1.0x/Short 1.0x → Long 5.0x/Short 3.0x)" in diff


def test_compute_diff_summary_does_not_flag_leverage_when_unchanged():
    cfg1 = _base_config()
    cfg2 = _base_config()

    diff = cfg1.compute_diff_summary(cfg2)
    assert "Leverage" not in diff


def test_compute_diff_summary_detects_calc_on_order_fills_change_in_tick_mode():
    cfg1 = BacktestRunConfig(
        strategy_key="ema_crossover",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=10_000.0,
        start_time=None,
        end_time=None,
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
        calc_on_order_fills=False,
    )
    cfg2 = BacktestRunConfig(
        strategy_key=cfg1.strategy_key,
        timeframe=cfg1.timeframe,
        initial_balance=cfg1.initial_balance,
        start_time=cfg1.start_time,
        end_time=cfg1.end_time,
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
        calc_on_order_fills=True,
    )

    diff = cfg1.compute_diff_summary(cfg2)
    assert "Calc on order fills (False → True)" in diff


def test_compute_diff_summary_ignores_calc_on_order_fills_outside_tick_mode():
    """BOT-077 §2/§6 — the flag is meaningless in `BAR_CLOSE` mode; flagging
    it there would read as a change that has no actual effect on the run."""
    cfg1 = _base_config()
    cfg2 = BacktestRunConfig(
        strategy_key=cfg1.strategy_key,
        timeframe=cfg1.timeframe,
        initial_balance=cfg1.initial_balance,
        start_time=cfg1.start_time,
        end_time=cfg1.end_time,
        calc_on_order_fills=True,
    )

    diff = cfg1.compute_diff_summary(cfg2)
    assert "Calc on order fills" not in diff


def test_fsm_run_restored_from_history_lands_on_completed_from_every_non_busy_state():
    """`BOT-095G` — picking an older run off the session history dropdown
    is a real previously-completed run being redisplayed, allowed from any
    state the screen can be idling in, but never from a busy one (a
    background action already owns the screen)."""
    non_busy_states = (
        BacktestUiState.IDLE,
        BacktestUiState.COMPLETED,
        BacktestUiState.CONFIG_DIRTY,
        BacktestUiState.EMPTY_DATA,
        BacktestUiState.ERROR,
    )
    for state in non_busy_states:
        assert (
            BACKTEST_STATE_TRANSITIONS[
                (state, BacktestUiEvent.RUN_RESTORED_FROM_HISTORY)
            ]
            == BacktestUiState.COMPLETED
        )

    busy_states = (
        BacktestUiState.RUNNING,
        BacktestUiState.CANCELLING,
        BacktestUiState.SYNCING,
    )
    for state in busy_states:
        assert (state, BacktestUiEvent.RUN_RESTORED_FROM_HISTORY) not in (
            BACKTEST_STATE_TRANSITIONS
        )
