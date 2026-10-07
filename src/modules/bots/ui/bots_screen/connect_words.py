"""`EPIC-034D` — what the Connect step says, in the user's words.

One sentence per failure kind lives with the application
(`connect_failure_words.py`), so Start answers in the same words the strip
shows; this adds how to read again. The Trading screen words the same kinds
for its status bar (`modules/trading/ui/market/connection_words.py`); a module
may not import another's `ui/`, and this sentence says what a bot's owner does
next, so the two are written apart.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    error_cause,
    failure_cause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)

CONNECTING = "Reading the account…"
NOT_CONNECTED = "No bot selected."
CONNECTED = "Connected"
NOT_CONNECTED_STATUS = "Not connected"
CONNECTING_STATUS = "Connecting…"

#: Said after a failure of a bot's venue, whose account Bots → Retry venue
#: account reads again; the Mainnet account window is opened again instead.
RETRY_VENUE_ACCOUNT = "Then choose Bots → Retry venue account."


def failure_sentence(failure: ConnectFailure) -> str:
    return f"{failure_cause(failure)} {RETRY_VENUE_ACCOUNT}"


def failure_sentence_for_error(error: str) -> str:
    return f"{error_cause(error)} {RETRY_VENUE_ACCOUNT}"
