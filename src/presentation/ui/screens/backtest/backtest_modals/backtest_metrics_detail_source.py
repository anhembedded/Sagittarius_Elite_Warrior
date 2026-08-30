"""`BacktestMetricsDetailSource` — translates `BackTestViewModel`'s retained
run data into the seven plain `get_*` callbacks `MetricsDetailVM` wants.

Kept apart from `metrics_detail_dialog.py` (the `QDialog` composition root
that constructs this and wires it in) per `architecture-rule.md` §5: a
translation adapter and the widget wiring that constructs it are different
abstraction levels and do not share a file — the same split
`backtest_symbol_picker_source.py`/`symbol_picker_dialog.py` and
`backtest_time_range_source.py`/`time_range_picker_dialog.py` already use.

@par Where each of the six data-bearing callbacks comes from
`BackTestViewModel.extended_metrics_snapshot()` (an `ExtendedMetricsSnapshot`,
plain Python accessor, not a QML `Property` — see that type's own module
docstring) is `BackTestPresenter._on_backtest_succeeded`'s one retention of
the just-finished run's real `BacktestMetrics` fields, set at the same place
`set_stat_cards(...)` already runs. `None` before the first successful run
(or after an empty/failed one) reads as "nothing to show yet" — every
callback below falls back to `_EMPTY_SNAPSHOT`'s zero/empty values rather
than raising, the same "0 trades means every card reads 0/neutral, never
'no cards'" convention `_on_backtest_succeeded`'s own docstring names for the
QML-facing stat cards.

@par `get_timeframe_seconds`
Reuses `describe_timeframe()` against the *current* `selectedTimeframe`
(not the snapshot — this one value is read live, per the task's own
instruction) — the exact pattern `BacktestTimeRangeSource.get_timeframe_seconds`
already uses, fallback constant duplicated rather than shared: that same
`_FALLBACK_TIMEFRAME_SECONDS = 60` already appears standalone in
`backtest_time_range_source.py`, `data_management_view.py`,
`data_management_widgets/time_range_card.py`, and `dev_board_panel.py` — a
fifth copy matches this codebase's own established convention rather than
inventing a new shared constant nobody asked for.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    describe as describe_timeframe,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.extended_metrics_snapshot import (
    ExtendedMetricsSnapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.performance_metrics_view import (
    StatCardData,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

#: Same fallback value/reasoning as `backtest_time_range_source.py`'s own
#: copy — see this module's docstring for why it is not shared.
_FALLBACK_TIMEFRAME_SECONDS = 60

_EMPTY_SNAPSHOT = ExtendedMetricsSnapshot(
    cards=(),
    gross_profit=0.0,
    gross_loss=0.0,
    profit_factor=0.0,
    total_closed_trades=0,
    fee_rate_percent=0.0,
)


class BacktestMetricsDetailSource:
    """Reads `BackTestViewModel`'s retained extended-metrics snapshot plus
    its live `selectedTimeframe`, in exactly the shape
    `MetricsDetailVM.__init__`'s seven `get_*` parameters need."""

    def __init__(self, view_model: BackTestViewModel) -> None:
        self._view_model = view_model

    def get_cards(self) -> Sequence[StatCardData]:
        return self._snapshot().cards

    def get_gross_profit(self) -> float:
        return self._snapshot().gross_profit

    def get_gross_loss(self) -> float:
        return self._snapshot().gross_loss

    def get_profit_factor(self) -> float:
        return self._snapshot().profit_factor

    def get_total_closed_trades(self) -> int:
        return self._snapshot().total_closed_trades

    def get_fee_rate_percent(self) -> float:
        return self._snapshot().fee_rate_percent

    def get_timeframe_seconds(self) -> int:
        option = describe_timeframe(self._view_model.selectedTimeframe)
        return option.seconds if option is not None else _FALLBACK_TIMEFRAME_SECONDS

    def _snapshot(self) -> ExtendedMetricsSnapshot:
        snapshot = self._view_model.extended_metrics_snapshot()
        return snapshot if snapshot is not None else _EMPTY_SNAPSHOT
