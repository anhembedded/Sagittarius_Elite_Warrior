"""`BOT-176` — what Export plan… asks: which bots, with which wanted state, and what to do with the text.

The dialog knows nothing about files, the dispatcher or the clipboard: it returns the
person's choice (`ExportPlanChoice`) or `None`, and `plan_export.py` does the rest.
Injectable (`AskExportPlan`) so a test exports without a modal dialog.

The risk is one direction: a bot running on the desktop arrives as "running" on a server
that starts planned bots (`--start-planned`). So the wanted state is a visible choice, and
it defaults to *All stopped* whenever the bots in scope include one on a mainnet venue.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label


class ExportPlanScope(Enum):
    SELECTED = "selected"
    ALL = "all"


class ExportPlanAction(Enum):
    SAVE = "save"
    COPY = "copy"


@dataclass(frozen=True, slots=True)
class ExportPlanChoice:
    scope: ExportPlanScope
    all_stopped: bool
    action: ExportPlanAction


#: `(every bot, the selected one or None)` -> the choice, or `None` when cancelled.
type AskExportPlan = Callable[
    [Sequence[BotSnapshot], BotSnapshot | None], ExportPlanChoice | None
]

NOTE = (
    "A plan holds no API key. The server judges it again with its own account: "
    "run `bot apply <file> --dry-run` first, then `bot apply <file>`."
)
SAVE_TEXT = "Save…"
COPY_TEXT = "Copy JSON"


def default_all_stopped(bots: Sequence[BotSnapshot]) -> bool:
    """*All stopped* is the default when any of `bots` trades real money."""
    return any(bot.venue.is_mainnet for bot in bots)


class ExportPlanDialog(QDialog):
    """@brief Asks which bots to export and how."""

    def __init__(
        self,
        bots: Sequence[BotSnapshot],
        selected: BotSnapshot | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export plan")
        self._bots = tuple(bots)
        self._selected = selected
        self._action = ExportPlanAction.SAVE
        self._state_chosen = False

        self.selected_only = QRadioButton(
            f"Selected bot ({selected.name})" if selected else "Selected bot"
        )
        self.selected_only.setObjectName("radioExportSelected")
        self.every_bot = QRadioButton(f"All bots ({len(self._bots)})")
        self.every_bot.setObjectName("radioExportAll")
        scope_group = QButtonGroup(self)
        scope_group.addButton(self.selected_only)
        scope_group.addButton(self.every_bot)
        self.selected_only.setEnabled(selected is not None)
        (self.selected_only if selected else self.every_bot).setChecked(True)

        self.keep = QRadioButton("Keep each bot's wanted state")
        self.keep.setObjectName("radioExportKeep")
        self.stopped = QRadioButton("All stopped")
        self.stopped.setObjectName("radioExportStopped")
        state_group = QButtonGroup(self)
        state_group.addButton(self.keep)
        state_group.addButton(self.stopped)
        self._apply_default_state()
        self.keep.clicked.connect(self._state_was_chosen)
        self.stopped.clicked.connect(self._state_was_chosen)
        scope_group.buttonToggled.connect(self._scope_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        save = buttons.addButton(SAVE_TEXT, QDialogButtonBox.ButtonRole.AcceptRole)
        save.setObjectName("btnExportSave")
        copy = buttons.addButton(COPY_TEXT, QDialogButtonBox.ButtonRole.ActionRole)
        copy.setObjectName("btnExportCopy")
        save.clicked.connect(lambda: self._finish(ExportPlanAction.SAVE))
        copy.clicked.connect(lambda: self._finish(ExportPlanAction.COPY))
        buttons.rejected.connect(self.reject)

        note = plain_label(NOTE)
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        for widget in (
            plain_label("Which bots"),
            self.selected_only,
            self.every_bot,
            plain_label("Wanted state in the plan"),
            self.keep,
            self.stopped,
            note,
            buttons,
        ):
            layout.addWidget(widget)

    def _in_scope(self) -> tuple[BotSnapshot, ...]:
        if self.selected_only.isChecked() and self._selected is not None:
            return (self._selected,)
        return self._bots

    def _apply_default_state(self) -> None:
        stopped = default_all_stopped(self._in_scope())
        self.stopped.setChecked(stopped)
        self.keep.setChecked(not stopped)

    def _state_was_chosen(self) -> None:
        self._state_chosen = True

    def _scope_changed(self) -> None:
        """The default follows the scope until the person has picked a state."""
        if not self._state_chosen:
            self._apply_default_state()

    def _finish(self, action: ExportPlanAction) -> None:
        self._action = action
        self.accept()

    def choice(self) -> ExportPlanChoice:
        scope = (
            ExportPlanScope.SELECTED
            if self.selected_only.isChecked()
            else ExportPlanScope.ALL
        )
        return ExportPlanChoice(scope, self.stopped.isChecked(), self._action)


def ask_export_plan_with_dialog(
    parent: QWidget, bots: Sequence[BotSnapshot], selected: BotSnapshot | None
) -> ExportPlanChoice | None:
    dialog = ExportPlanDialog(bots, selected, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.choice()
