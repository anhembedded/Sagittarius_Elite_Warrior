"""`ITradingSession`, implemented over the commands the handlers already run.

**Why it dispatches instead of calling the handlers.** The same reasoning
`MarketStreamService` records next door in `market_data`: the handlers are
where the module logs what happened and turns a reconciliation into a result a
screen can show, and the CLI reaches two of them through the same dispatch. A
port that skipped them would leave two paths to the same state the day either
handler grows a rule.

**What it adds.** The translation, and nothing else: three commands in,
each addressed to this service's own venue, their own results out, and `read_all()`'s tuple mapped to the
published `TradingSessionSnapshot`. It decides nothing — not whether trading
may open, not what a generation clash means.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.ensure_session_ready.command import (
    EnsureSessionReadyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget.command import (
    RegisterOwnerBudgetCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
    TradingSessionSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _answered(response: object, expected: type) -> object:
    """A dispatch that answered with the wrong type, or nothing at all, is a
    **composition** fault — no handler bound, or a test double returning
    `None`. It is not a business outcome, so it raises here rather than being
    folded into a result the caller would read as a refusal.

    `IMarketStream.start()` makes the opposite choice, and deliberately:
    `StreamOutcome` has a `success` field designed to carry exactly this, so
    reporting it is honest there. `SessionReadyResult` has no such field —
    inventing `ready=False` for a broken container would tell the user
    trading was refused when nothing was even asked.

    `TypeError` rather than `RuntimeError` on ruff's `TRY004`, and the rule is
    right here: the fault really is "this object is the wrong type", and a
    caller debugging a container never has to catch it.
    """
    if not isinstance(response, expected):
        raise TypeError(
            f"the trading session dispatch was not answered with "
            f"{expected.__name__} but with {type(response).__name__} — no "
            f"handler is bound for it"
        )
    return response


class TradingSessionService(ITradingSession):
    """The module's answer to "is the session open, and open it", for
    one venue (`EPIC-028B`: one instance per venue, over that venue's own
    `TradingSessionState`)."""

    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        session_state: TradingSessionState,
        trading_venue: TradingVenue,
    ) -> None:
        self._dispatcher = dispatcher
        self._session_state = session_state
        self._trading_venue = trading_venue

    def snapshot(self) -> TradingSessionSnapshot:
        enabled, orders_sent, open_symbols = self._session_state.read_all()
        return TradingSessionSnapshot(
            enabled=enabled,
            orders_sent_this_session=orders_sent,
            known_open_symbols=open_symbols,
            market_type=self._trading_venue.market_type,
            spot_baseline_holdings=self._session_state.spot_baseline_holdings(),
        )

    def ensure_ready(self) -> SessionReadyResult:
        response = self._dispatcher.dispatch(
            EnsureSessionReadyCommand,
            EnsureSessionReadyCommand(venue=self._trading_venue),
        )
        return _answered(response, SessionReadyResult)  # type: ignore[return-value]

    def claim_symbol(self, symbol: str, owner_id: str) -> bool:
        """Straight to the state, not through a command: a lease claim is a
        state mutation with no exchange round trip and nothing to reconcile —
        the shape `snapshot()` already uses for the read side. A command would
        add a dispatcher hop and a result type around one dict write.
        """
        return self._session_state.claim_symbol(symbol, owner_id)

    def lease_holder(self, symbol: str) -> str | None:
        return self._session_state.lease_holder(symbol)

    def release_symbol(self, symbol: str, owner_id: str) -> None:
        self._session_state.release_symbol(symbol, owner_id)

    def register_owner_budget(
        self, registration: OwnerBudgetRegistration
    ) -> OwnerBudgetRegistrationResult:
        """Dispatched: the registration reads the venue's history, the same
        reason `ensure_ready()` goes through its handler."""
        response = self._dispatcher.dispatch(
            RegisterOwnerBudgetCommand,
            RegisterOwnerBudgetCommand(registration, venue=self._trading_venue),
        )
        return _answered(response, OwnerBudgetRegistrationResult)  # type: ignore[return-value]

    def clear_owner_budget(self, owner_id: str) -> None:
        """Straight to the state, as the lease is: a dict removal with nothing
        to reconcile."""
        self._session_state.owner_books.clear_owner(owner_id)

    def emergency_stop(self) -> EmergencyStopResult:
        response = self._dispatcher.dispatch(
            EmergencyStopCommand, EmergencyStopCommand(venue=self._trading_venue)
        )
        return _answered(response, EmergencyStopResult)  # type: ignore[return-value]
