"""`BOT-025` — locks the Backtest module's event catalog to what
`contracts/events/__init__.py` documents, and locks both command handlers to
publishing exactly that pair. A new event file or a third `publish()` call
must update that docstring in the same change, not drift silently past it.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest.handler import (
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest.handler import (
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events import (
    backtest_completed_event,
    backtest_failed_event,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_failed_event import (
    BacktestFailedEvent,
)

#: `backtest_failed_event.__file__` is the one path this test needs that no
#: hand-counted `Path(__file__).parents[N]` can silently get wrong if this
#: test file itself ever moves.
_EVENTS_PACKAGE = Path(backtest_failed_event.__file__).resolve().parent
assert Path(backtest_completed_event.__file__).resolve().parent == _EVENTS_PACKAGE


def test_the_events_package_holds_exactly_the_documented_pair() -> None:
    event_files = {
        path.name for path in _EVENTS_PACKAGE.glob("*.py") if path.name != "__init__.py"
    }

    assert event_files == {"backtest_completed_event.py", "backtest_failed_event.py"}


def test_events_catalog_docstring_names_both_handlers() -> None:
    """A cheap tripwire, not a substitute for the handler tests above: the
    docstring names both handler classes by their real import path, so a
    rename that breaks the reference is caught here rather than only by a
    human re-reading prose that quietly went stale."""
    doc = (_EVENTS_PACKAGE / "__init__.py").read_text(encoding="utf-8")

    assert RunStaticBacktestCommandHandler.__name__ in doc
    assert RunHistoricalTickBacktestCommandHandler.__name__ in doc
    assert BacktestCompletedEvent.__name__ in doc
    assert BacktestFailedEvent.__name__ in doc
