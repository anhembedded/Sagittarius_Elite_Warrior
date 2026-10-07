"""`EPIC-034D` — what the Connect step shows, as one immutable value.

Built from the step's state and the last answer, so the identity strip, the
chart's lock and the Plan's lock all read the same words and the same
decision. A pure function: each sentence is tested without a widget.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_connect_fsm_matrix import (
    ConnectState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_words import (
    CONNECTED,
    CONNECTING,
    CONNECTING_STATUS,
    NOT_CONNECTED,
    NOT_CONNECTED_STATUS,
    failure_sentence,
    failure_sentence_for_error,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


@dataclass(frozen=True, slots=True)
class ConnectView:
    state: ConnectState = ConnectState.NOT_CONNECTED
    #: The venue's title, never its identifier; empty with no bot selected.
    venue: str = ""
    status: str = NOT_CONNECTED_STATUS
    #: The balances line when connected, the reason when not.
    detail: str = NOT_CONNECTED

    @property
    def locked(self) -> bool:
        """The chart and the Plan wait: a bot is selected and its account has
        not been read."""
        return self.state in (ConnectState.CONNECTING, ConnectState.FAILED)

    @property
    def can_retry(self) -> bool:
        return self.state is ConnectState.FAILED

    @property
    def lock_reason(self) -> str:
        return f"{self.venue}: {self.detail}" if self.locked else ""


def connecting_view(source: AccountSource) -> ConnectView:
    return ConnectView(
        ConnectState.CONNECTING, source.venue_title, CONNECTING_STATUS, CONNECTING
    )


def connected_view(snapshot: VenueAccountSnapshot) -> ConnectView:
    available = write_value(ColumnKind.MONEY, float(snapshot.available))
    return ConnectView(
        ConnectState.CONNECTED,
        snapshot.source.venue_title,
        CONNECTED,
        f"{available} {snapshot.quote_asset} available · {_key_words(snapshot)}",
    )


def failed_view(failure: ConnectFailure) -> ConnectView:
    return ConnectView(
        ConnectState.FAILED,
        failure.source.venue_title,
        NOT_CONNECTED_STATUS,
        failure_sentence(failure),
    )


def errored_view(source: AccountSource, error: str) -> ConnectView:
    return ConnectView(
        ConnectState.FAILED,
        source.venue_title,
        NOT_CONNECTED_STATUS,
        failure_sentence_for_error(error),
    )


def start_refusal(view: ConnectView) -> str:
    """Why Start waits on the account: it has not been read; empty once it was.
    Whether the key may trade is a constraint on the plan
    (`KEY_CANNOT_TRADE`, `EPIC-034F`), judged with the rest, not a second
    place that says so."""
    return view.lock_reason


def _key_words(snapshot: VenueAccountSnapshot) -> str:
    if snapshot.can_trade is None:
        return "key permission unknown"
    return "key can trade" if snapshot.can_trade else "key cannot trade"
