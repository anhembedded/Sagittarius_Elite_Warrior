"""`EPIC-034D` — what the Connect step's answer does to the screen.

The chart and the Plan open only once the venue's account was read (D1): the
chart's place says why while it waits, the Plan is disabled, Start's reason
names the connection, and the identity strip shows the result. Held apart from
`ConnectStep` so that the step stays a lifecycle and a read, and the presenter
only constructs this and asks it for the chart.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_chart_host import (
    BotChartHost,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_step import (
    ConnectStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    ConnectView,
    start_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
        BotsView,
    )


class ConnectEffects:
    """@brief Applies each `ConnectView` to the model, the chart and Start."""

    def __init__(
        self,
        step: ConnectStep,
        view: BotsView,
        charts: BotChartHost,
        selected: SelectedBot,
        refresh_detail: Callable[[], None],
    ) -> None:
        self._step = step
        self._view = view
        self._model = view.model
        self._charts = charts
        self._selected = selected
        self._refresh_detail = refresh_detail
        step.changed.connect(self._apply)
        view.model.retry_connect_requested.connect(step.retry)

    def present_chart(self, bot: BotSnapshot | None) -> None:
        """The bot's chart once its account was read, else why there is none."""
        connection = self._model.connect_view
        if bot is not None and connection.locked:
            # Closing releases the chart's stream and turns the Live stream
            # command off, so Go live is not offered on a chart nobody sees
            # until the account was read (`EPIC-034G` handed this gate over).
            self._charts.close()
            self._view.lock_chart(connection.lock_reason)
        else:
            self._view.set_chart(self._charts.show(bot))

    def _apply(self, connection: ConnectView) -> None:
        self._model.set_connect(connection)
        self._selected.connection = start_refusal(connection, self._step.snapshot)
        self.present_chart(self._model.selected)
        self._refresh_detail()
