"""`EPIC-034H` — Bots → Fix next item: do the first fix the readiness offers.

Each item left before Start names its fix (`ReadinessFix`); this is the one
command that performs it, in the order the items are listed: read the account
again, bring the field a design item is about forward, or select the bot that
is still active so Stop is one command away. The command is enabled exactly
while there is such an item (`next_fix`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_step import (
    ConnectStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.readiness_words import (
    next_fix,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)


class FixNextItem:
    """@brief Performs the first available fix on the selected bot."""

    def __init__(
        self, model: BotsViewModel, selected: SelectedBot, step: ConnectStep
    ) -> None:
        self._model = model
        self._selected = selected
        self._step = step
        model.fix_next_requested.connect(self.perform)

    def available(self, readiness: BotReadiness | None) -> bool:
        """Whether `readiness` has an item whose fix this can do."""
        return self._next(readiness) is not None

    def perform(self) -> None:
        item = self._next(self._model.readiness)
        panel = self._selected.panel
        if item is None:
            return
        if item.fix is ReadinessFix.RETRY_CONNECTION:
            self._step.retry()
        elif item.fix is ReadinessFix.STOP_OTHER_BOT:
            self._model.select_requested.emit(item.target)
        elif panel is not None:
            panel.focus_field(item.target)

    def _next(self, readiness: BotReadiness | None) -> ReadinessItem | None:
        panel = self._selected.panel
        if readiness is None:
            return None
        return next_fix(readiness, panel.field_label if panel else lambda _code: None)
