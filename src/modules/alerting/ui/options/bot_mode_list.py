"""The "Bots" list of the Alerts page: each bot and what it may tell (`BOT-191`, `EPIC-036D6`).

Split from the page's presenter, which was at the file-size ceiling: this part has one reason to
change (how a bot's alert mode is listed and kept) and the presenter keeps the one tracker, relay
and status line. `read` and `keep` do disk work and run on the pool; `show` and `show_again` touch
the view model and run on the UI thread.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
    BotModeRow,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)


class BotModeList:
    def __init__(
        self,
        modes: IBotAlertModes,
        dispatcher: ICommandDispatcher,
        view_model: AlertsSettingsViewModel,
    ) -> None:
        self._modes = modes
        self._dispatcher = dispatcher
        self._view_model = view_model

    @property
    def read_only(self) -> bool:
        return self._modes.read_only

    def read(self) -> tuple[BotModeRow, ...]:
        """The bots the page can set, each with what it may tell now. Runs on the pool: the
        report reads every bot's file."""
        report = cast(
            BotStatusReport,
            self._dispatcher.dispatch(
                GetBotStatusReportQuery, GetBotStatusReportQuery()
            ),
        )
        modes = self._modes.modes()
        return tuple(
            BotModeRow(
                entry.bot_id,
                entry.name,
                modes.get(entry.bot_id, BotAlertMode.ON).value,
            )
            for entry in report.bots
        )

    def keep(self, bot_id: str, mode: BotAlertMode) -> BotAlertMode:
        """Sets and keeps one bot's mode. Runs on the pool: it writes the settings file."""
        self._modes.set_mode(bot_id, mode)
        return mode

    def show(self, rows: tuple[BotModeRow, ...]) -> None:
        read_only = self._modes.read_only
        note = (
            alerts_words.READ_ONLY_NOTE
            if read_only
            else ("" if rows else alerts_words.NO_BOTS)
        )
        self._view_model.set_bot_rows(rows, note, editable=not read_only)

    def show_again(self) -> None:
        """Memory only: the same bots, each with the mode really kept now."""
        modes = self._modes.modes()
        self.show(
            tuple(
                replace(row, mode=modes.get(row.bot_id, BotAlertMode.ON).value)
                for row in self._view_model.bot_rows
            )
        )
