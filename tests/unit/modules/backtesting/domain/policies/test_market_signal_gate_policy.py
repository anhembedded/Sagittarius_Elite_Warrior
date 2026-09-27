"""EPIC-027B — `MarketSignalGatePolicy`: which signals a market can execute."""

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.market_signal_gate_policy import (
    MarketSignalGatePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("action", list(SignalAction))
def test_usd_m_futures_admits_every_action(action: SignalAction):
    assert MarketSignalGatePolicy(MarketType.FUTURES_USD_M).admits(action) is True


@pytest.mark.parametrize(
    ("action", "admitted"),
    [
        (SignalAction.BUY, True),
        (SignalAction.SELL, True),
        (SignalAction.HOLD, True),
        (SignalAction.SHORT, False),
        (SignalAction.COVER, False),
    ],
)
def test_spot_refuses_only_the_short_side(action: SignalAction, admitted: bool):
    assert MarketSignalGatePolicy(MarketType.SPOT).admits(action) is admitted


def test_record_refusal_counts_each_call():
    gate = MarketSignalGatePolicy(MarketType.SPOT)

    gate.record_refusal(SignalAction.SHORT, _T0)
    gate.record_refusal(SignalAction.COVER, _T0)

    assert gate.refused_count == 2


def test_a_market_that_refuses_nothing_logs_no_run_summary(caplog):
    caplog.set_level("INFO", logger="App.PaperExchange")

    MarketSignalGatePolicy(MarketType.FUTURES_USD_M).log_run_summary()

    assert not [r for r in caplog.records if "[spot-gate]" in r.getMessage()]
