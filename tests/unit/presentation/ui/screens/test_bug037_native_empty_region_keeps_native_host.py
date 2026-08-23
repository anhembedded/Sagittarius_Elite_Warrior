"""BUG-037 regression — an empty region/info payload must not kill the native host.

`BackTestPresenter._emit_strategy_trend_zones()` emits its signal on **every**
backtest run, including for the majority of strategies that never override
`classify_trend_zone()` and therefore produce an empty span list. Its docstring
calls that "one no-op signal emit", which was true of the Python host but not of
the native one: `NativeBacktestChartHostAdapter.set_script_regions()` raised
`NativeUnsupportedFeatureError` without ever looking at `spans`, so the
presenter tore the native chart down and rebuilt it with Python on every run,
for every strategy — silently discarding the whole BOT-098F native path at
runtime while the startup log still said `backend 'native'`.

The contract these tests pin down: the adapter may only refuse work it is
actually being asked to *draw*. Being handed nothing to draw is satisfiable, and
is already how `clear_script_regions()`/`clear_script_info()` behave.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_host_adapter import (
    NativeBacktestChartHostAdapter,
    NativeUnsupportedFeatureError,
)

_A_SPAN = (1_700_000_000.0, 1_700_000_060.0, "#0ECB81", 0.15)
_AN_INFO_FIELD = ("Trend", "UP", "#0ECB81")


@pytest.fixture
def fake_native_host(qapp):
    host = Mock(spec=NativeBacktestChartHost)
    host.widget = ChartCard("placeholder")
    host.submit_ohlcv.return_value = True
    host.submit_indicators.return_value = True
    host.submit_markers.return_value = True
    return host


@pytest.fixture
def adapter(qapp, request, fake_native_host):
    result = NativeBacktestChartHostAdapter("BTCUSDT", fake_native_host)
    request.addfinalizer(result.widget.deleteLater)
    return result


def test_empty_spans_do_not_raise(adapter):
    """The exact call every non-trend-zone strategy makes on every run.

    Before the fix this raised, which is what dropped the native host.
    """
    adapter.set_script_regions("strategy_trend_zone", [])


def test_empty_info_fields_do_not_raise(adapter):
    adapter.set_script_info("strategy_trend_zone", [])


def test_non_empty_spans_are_still_rejected(adapter):
    """The real limitation must survive: native has no background-region ABI.

    This is the half of the contract that must NOT be relaxed — otherwise
    trend zones would be silently dropped instead of falling back to Python.
    """
    with pytest.raises(NativeUnsupportedFeatureError, match="regions"):
        adapter.set_script_regions("strategy_trend_zone", [_A_SPAN])


def test_non_empty_info_fields_are_still_rejected(adapter):
    with pytest.raises(NativeUnsupportedFeatureError, match="info"):
        adapter.set_script_info("some_script", [_AN_INFO_FIELD])


def test_an_empty_payload_draws_nothing_on_the_native_host(adapter, fake_native_host):
    """Accepting the call must not turn into a stray native submission.

    "No-op" has to mean no-op — quietly submitting an empty snapshot would
    burn a generation token and could invalidate a legitimate later one.
    """
    adapter.set_script_regions("strategy_trend_zone", [])
    adapter.set_script_info("strategy_trend_zone", [])

    fake_native_host.submit_ohlcv.assert_not_called()
    fake_native_host.submit_indicators.assert_not_called()
    fake_native_host.submit_markers.assert_not_called()


def test_empty_payload_leaves_the_adapter_usable_for_real_work(
    adapter, fake_native_host
):
    """The end-to-end point of the bug: the host survives and still renders.

    A run that emits zero trend zones must leave the native adapter in a state
    where the actual chart data still lands on it — that is precisely what
    stopped happening.
    """
    adapter.set_script_regions("strategy_trend_zone", [])

    adapter.render_historical_data([(1_700_000_000.0, 10.0, 12.0, 9.0, 11.0)])
    adapter.render_historical_volume([(1_700_000_000.0, 100.0, True)])

    fake_native_host.submit_ohlcv.assert_called_once()
