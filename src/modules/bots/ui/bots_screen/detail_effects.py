"""`EPIC-029F` — what a fresh judgement of the selected bot does to the screen.

One refresh recomputes the bot's detail (`SelectedBot.detail`) and applies it:
the figures, the verdicts and what blocks Start, which actions are live, the
levels drawn on the chart, the message on each parameter field
(`EPIC-034F`) and the backtest page. Held apart from `BotsPresenter` so the
presenter stays an orchestrator of reads and actions.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_chart_host import (
    BotChartHost,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_step import (
    ConnectStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fix_next_item import (
    FixNextItem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.kind_backtests import (
    KindBacktests,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)


class DetailEffects:
    """@brief Applies the selected bot's detail to the model, chart and editor."""

    def __init__(
        self,
        selected: SelectedBot,
        model: BotsViewModel,
        charts: BotChartHost,
        backtests: KindBacktests,
        step: ConnectStep,
    ) -> None:
        self._step = step
        self._fixes = FixNextItem(model, selected, step)
        self._selected = selected
        self._model = model
        self._charts = charts
        self._backtests = backtests

    def refresh(self) -> None:
        detail = self._selected.detail()
        self._model.set_facts(detail.facts if detail else None)
        self._model.set_judgement(detail.verdict_lines if detail else ())
        readiness = detail.readiness if detail else None
        self._step.assessed(readiness)
        self._model.set_readiness(
            readiness, self._step.state, self._fixes.available(readiness)
        )
        self._model.set_availability(detail.availability if detail else {})
        self._charts.draw(detail.overlay if detail else None)
        panel = self._selected.panel
        if panel is not None:
            panel.show_verdicts(detail.verdicts if detail else ())
        self._backtests.follow(self._selected)
