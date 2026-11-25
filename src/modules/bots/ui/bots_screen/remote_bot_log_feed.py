"""`EPIC-047F` — the VPS tab's log panel is fed with the selected bot's own lines from the host, read-only.

@details The same panel, model and `append_log_line` as the Bots tab (AC7): this class replaces only where the lines come from.
While a bot is selected it asks the host for the lines after its cursor every `POLL_MS`, one read at a time on the app's pool
(`FencedReads`), and a late answer for a bot that is no longer selected is dropped. Nothing is asked for a bot that is not
selected, nothing is held open between asks, and nothing here sends a command. Switching bots moves the cursor to the new bot's own;
a bot seen before only asks for what is newer, so a line is never shown twice.

The model's `log_note` carries what the source says of itself: how old the last line is (by the minute, so the panel is redrawn at
most once a minute, never under the reader's scroll), and why there is nothing when the host cannot be read.

@par Extension cases
  · a second host's log - another `IVpsTab` behind another route; this class names no host;
  · following a bot that is not selected - one more cursor and one more read kind; the panel shows the selected bot only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QObject, QTimer, Signal
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_log_chunk import (
    BotLogChunk,
    BotLogLineOfTheHost,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    FencedReads,
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
        BotsViewModel,
    )

#: How often the selected bot's log is asked for; a read of a local file on the host, a few hundred bytes a call.
POLL_MS: Final = 2000
_MINUTE_S: Final = 60
_HOUR_S: Final = 3600

type AskTheHost = Callable[[str, int], BotLogChunk]


class RemoteBotLogFeed(QObject):
    """@brief Polls the host's log of the selected bot; never of another."""

    line = Signal(str)

    def __init__(
        self,
        ask: AskTheHost,
        threads: IThreadManager,
        now: Callable[[], datetime],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ask = ask
        self._now = now
        self._reads = FencedReads(threads, {ReadKind.LOG: ActionOwnershipTracker()})
        self._reads.answered.connect(self._answered)
        self._reads.failed.connect(self._failed)
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._ask_for_the_log)
        self._model: BotsViewModel | None = None
        self._cursors: dict[str, int] = {}
        self._last_line_at: dict[str, datetime] = {}
        self._in_flight = False
        self._closed = False

    def feed_model(self, model: BotsViewModel) -> None:
        self._model = model
        self.line.connect(model.append_log_line)
        model.selection_changed.connect(self._selection_changed)
        self._timer.start()
        self._selection_changed()

    def close(self) -> None:
        self._closed = True
        self._timer.stop()
        self._reads.drop_all()

    # -- what is selected ---------------------------------------------------------------------

    def _selected_bot_id(self) -> str | None:
        bot = self._model.selected if self._model is not None else None
        return bot.bot_id if bot is not None else None

    def _selection_changed(self) -> None:
        bot_id = self._selected_bot_id()
        self._in_flight = False
        if self._model is not None:
            self._model.set_log_note(self._age_note(bot_id) if bot_id else "")
        self._ask_for_the_log()

    def _ask_for_the_log(self) -> None:
        bot_id = self._selected_bot_id()
        if bot_id is None or self._closed or self._in_flight:
            return
        since = self._cursors.get(bot_id, 0)
        self._in_flight = True
        self._reads.read(ReadKind.LOG, bot_id, lambda: self._ask(bot_id, since))

    # -- answers (the UI thread) --------------------------------------------------------------

    def _answered(self, _kind: object, bot_id: str, answer: object) -> None:
        self._in_flight = False
        if bot_id != self._selected_bot_id() or not isinstance(answer, BotLogChunk):
            return
        for host_line in answer.lines:
            self.line.emit(_line_of(bot_id, host_line))
        if answer.lines:
            self._last_line_at[bot_id] = _moment(answer.lines[-1].at, self._now())
        self._cursors[bot_id] = max(self._cursors.get(bot_id, 0), answer.next_since)
        if self._model is not None:
            self._model.set_log_note(self._age_note(bot_id))

    def _failed(self, _kind: object, bot_id: str, words: str) -> None:
        self._in_flight = False
        if bot_id == self._selected_bot_id() and self._model is not None:
            self._model.set_log_note(f"the host's log is not readable now: {words}")

    def _age_note(self, bot_id: str | None) -> str:
        if bot_id is None or bot_id not in self._last_line_at:
            return "no line from the host yet" if bot_id in self._cursors else ""
        seconds = int((self._now() - self._last_line_at[bot_id]).total_seconds())
        if seconds < _MINUTE_S:
            return "the host's last line is under a minute old (host times are UTC)"
        if seconds < _HOUR_S:
            return f"the host's last line is {seconds // _MINUTE_S} min old (host times are UTC)"
        return (
            f"the host's last line is {seconds // _HOUR_S} h old (host times are UTC)"
        )


def _line_of(bot_id: str, line: BotLogLineOfTheHost) -> str:
    """The Bots tab's own shape, `HH:MM:SS LEVEL message`, with the host's clock."""
    return f"{line.at[11:19]} {line.level} Bot {bot_id}: {line.text}"


def _moment(text: str, fallback: datetime) -> datetime:
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return fallback
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
