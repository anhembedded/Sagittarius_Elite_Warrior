"""`BUG-203` - a Futures Grid's own opening fills are not warnings.

@details Binance may report the position (`ACCOUNT_UPDATE`) before the fill that moved it
(`ORDER_TRADE_UPDATE`). For the seconds between them the owner's derived position lags the
exchange by exactly one fill: a snapshot disagreement, not yet a divergence. The bot's watch
confirms after a re-read and says so itself when the divergence is real, so the opening of a
healthy run writes no WARNING (the run-log scan fails a run that has one), while a position
nobody here opened still halts the bot and is warned about by the watch.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from .futures_bots_world import booted_futures_bots
from .futures_direction_scenarios import LONG
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import _started
from .test_every_direction_passes_the_shared_journeys_on_the_fake_exchange import (
    _by_hand,
)
from .test_the_streams_ordering_gap_costs_the_exchange_nothing_on_the_fake_exchange import (
    _account_report_first,
    _deliver,
    _the_entry_fills,
    _the_recheck_delay_passes,
)


class _Warnings(logging.Handler):
    """The WARNING-or-worse records of the `App.*` loggers, which do not propagate to `caplog`."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(f"{record.name}: {record.getMessage()}")


@contextmanager
def _watching_warnings() -> Iterator[_Warnings]:
    handler, root = _Warnings(), logging.getLogger("App")
    root.addHandler(handler)
    try:
        yield handler
    finally:
        root.removeHandler(handler)


def test_an_opening_fill_the_account_reports_first_logs_no_warning(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app, _watching_warnings() as warned:
        _started(app, LONG.config)
        _deliver(app, _account_report_first(_the_entry_fills(app)))
        _the_recheck_delay_passes(app)
        assert warned.lines == []


def test_a_position_nobody_here_opened_still_warns(futures: FakeExchange) -> None:
    with booted_futures_bots(futures) as app:
        _started(app, LONG.config)
        with _watching_warnings() as warned:
            _by_hand(app, LONG, "0.003")
            app.deliver()
            _the_recheck_delay_passes(app)
        assert any("[halt-closes-position]" in line for line in warned.lines), (
            "a confirmed foreign position is still warned about"
        )
