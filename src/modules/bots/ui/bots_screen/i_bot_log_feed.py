"""`EPIC-047F` — where the Bots screen's log lines come from: this computer's own bots (`BotLogFeed`) or the VPS host's (`RemoteBotLogFeed`).

@details A `Protocol`, because both implementers are `QObject`s (`architecture-rule.md` §2.1, reason a). The screen builds the
one its backend names (`BotsBackend.log_feed`), calls `feed_model(model)` once and `close()` at shutdown; `line` carries a formatted
line, newest last.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import SignalInstance

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
        BotsViewModel,
    )


class IBotLogFeed(Protocol):
    line: SignalInstance

    def feed_model(self, model: BotsViewModel) -> None:
        """Connects the feed to the screen's model: its lines, and (for a remote feed) its selection."""

    def close(self) -> None:
        """Stops the feed. Safe to call twice."""
