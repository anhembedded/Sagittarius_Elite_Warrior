"""`EPIC-040D` — handler for `RunBacktestQuery`.

Finds the kind by its id in the catalog and runs the kind's own backtester (`IBotKind.backtester`,
`EPIC-040B`), so the workbench dispatches one query and names no kind. A kind the catalog does not
know, or one with no backtest, is refused in words like any other period that cannot be replayed."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest.query import (
    RunBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestAnswer,
    BacktestRefusal,
)


class RunBacktestQueryHandler(IQueryHandler[RunBacktestQuery, BacktestAnswer]):
    def __init__(self, catalog: IBotKindCatalog) -> None:
        self._catalog = catalog

    def execute(self, query: RunBacktestQuery) -> BacktestAnswer:
        try:
            kind = self._catalog.kind(query.kind_id)
        except UnknownBotKindError:
            return BacktestRefusal(f"No kind of bot called {query.kind_id!r} is known.")
        backtester = kind.backtester()
        if backtester is None:
            return BacktestRefusal(f"A {query.kind_id!r} bot has no backtest.")
        return backtester.run(query.request)
