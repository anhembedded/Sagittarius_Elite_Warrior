"""`EPIC-034D` — what the Connect step shows, as one immutable value.

Built from the step's state and the last answer, so the identity strip, the
chart's lock and the Plan's lock all read the same words and the same
decision. A pure function: each sentence is tested without a widget.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.account_view import (
    account_view_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    ACCOUNT_UNREADABLE_STATE,
    state_words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    ConnectionRead,
    ConnectionState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_words import (
    CONNECTED,
    CONNECTING,
    CONNECTING_STATUS,
    NOT_CONNECTED,
    NOT_CONNECTED_STATUS,
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
    state: ReadinessState = ReadinessState.NOT_CONNECTED
    #: The venue's title, never its identifier; empty with no bot selected.
    venue: str = ""
    status: str = NOT_CONNECTED_STATUS
    #: The balances line when connected, the state in a few words when not
    #: ("key refused"): the advice is the message bar's alone (`BUG-181`).
    detail: str = NOT_CONNECTED
    #: What the readiness item for a failed read says (`EPIC-034H`): the same
    #: few words, "Not connected: key refused".
    cause: str = ""

    @property
    def locked(self) -> bool:
        """The chart and the Plan wait: a bot is selected and its account has
        not been read."""
        return self.state in (ReadinessState.CONNECTING, ReadinessState.FAILED)

    @property
    def can_retry(self) -> bool:
        return self.state is ReadinessState.FAILED

    @property
    def lock_reason(self) -> str:
        if self.state is ReadinessState.FAILED:
            return f"{self.venue}: {self.status}: {self.detail}"
        return f"{self.venue}: {self.detail}" if self.locked else ""


def connecting_view(source: AccountSource) -> ConnectView:
    return ConnectView(
        ReadinessState.CONNECTING, source.venue_title, CONNECTING_STATUS, CONNECTING
    )


def connected_view(snapshot: VenueAccountSnapshot) -> ConnectView:
    available = write_value(ColumnKind.MONEY, float(snapshot.available))
    return ConnectView(
        ReadinessState.DESIGNING,
        snapshot.source.venue_title,
        CONNECTED,
        f"{available} {snapshot.quote_asset} available · {_key_words(snapshot)}",
    )


def failed_view(failure: ConnectFailure) -> ConnectView:
    return _failed(failure.source, state_words(failure))


def errored_view(source: AccountSource) -> ConnectView:
    return _failed(source, ACCOUNT_UNREADABLE_STATE)


def _failed(source: AccountSource, state: str) -> ConnectView:
    return ConnectView(
        ReadinessState.FAILED,
        source.venue_title,
        NOT_CONNECTED_STATUS,
        state,
        f"{NOT_CONNECTED_STATUS}: {state}",
    )


def connection_read(
    view: ConnectView, snapshot: VenueAccountSnapshot | None
) -> ConnectionRead:
    """The Connect step's answer in the form the assessment takes
    (`EPIC-034H`): reading, failed with its cause, or connected with the
    account's numbers."""
    if view.state is ReadinessState.CONNECTING:
        return ConnectionRead(ConnectionState.READING, view.venue)
    if snapshot is None or view.state is ReadinessState.FAILED:
        return ConnectionRead(ConnectionState.FAILED, view.venue, reason=view.cause)
    return ConnectionRead(
        ConnectionState.CONNECTED, view.venue, account_view_of(snapshot)
    )


def _key_words(snapshot: VenueAccountSnapshot) -> str:
    if snapshot.can_trade is None:
        return "key permission unknown"
    return "key can trade" if snapshot.can_trade else "key cannot trade"
