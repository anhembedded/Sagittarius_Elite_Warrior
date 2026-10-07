"""`EPIC-034D` — what the Connect step says, in the user's words.

The advice for each failure kind lives with the application
(`connect_failure_words.py`) and is told once, in the message bar; the strip,
the chart's place and the Plan say the short state (`BUG-181`). The Trading
screen words the same kinds for its status bar
(`modules/trading/ui/market/connection_words.py`); a module may not import
another's `ui/`, and the advice says what a bot's owner does next, so the two
are written apart.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    NOT_CONNECTED as NOT_CONNECTED_WORDS,
)

CONNECTING = "Reading the account…"
NOT_CONNECTED = "No bot selected."
CONNECTED = "Connected"
NOT_CONNECTED_STATUS = NOT_CONNECTED_WORDS
CONNECTING_STATUS = "Connecting…"
