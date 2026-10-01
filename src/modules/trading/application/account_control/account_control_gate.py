"""`EPIC-028F` — the checks both Futures account-control commands pass
before anything is sent.

@details In order, each answered without the network until the last two:
1. the venue submits nothing (`DISABLED`) → `TRADING_VENUE_DISABLED`;
2. the venue has no leverage or margin mode (Spot, whose `VenueContext`
   holds no `IFuturesAccountControl`) → `NOT_A_FUTURES_VENUE`;
3. the venue's trading switch is off → `TRADING_SWITCH_OFF`: changing
   leverage is signed account activity, gated like a cancel;
4. a strategy manages the symbol → `SYMBOL_LEASED`: its next order would
   lock a different margin than it sized for; the order path refuses the
   same lease (PR #299 review, finding 4);
5. the connection check fails → `CONNECTION_NOT_READY`;
6. the symbol has an open position → `POSITION_OPEN`, with the position in
   `detail`. This is the app's own policy, not a claim about the exchange
   (`EPIC-028Q`): Binance refuses a margin-mode change with a position open,
   but may accept a leverage change, raising it at least; the app refuses
   both, so a position's margin and its liquidation estimate never change
   under it from the desk. Not yet checked against Testnet, which this
   repository's sessions cannot reach.
   The read goes through the control port, so it fails as the change does:
   a refusal of the read is `EXCHANGE_REJECTED`, an unknown outcome raises
   `AccountControlUnavailableError` (PR #299 review, finding 1).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class AccountControlRefused:
    """A check failed; nothing is sent."""

    blocked_by: ExecuteOrderSafetyGate | AccountControlRefusal
    detail: str | None = None


@dataclass(frozen=True)
class AccountControlCleared:
    """Every check passed; `control` is the venue's own."""

    control: IFuturesAccountControl


def clear_account_control(
    scopes: VenueTradingScopes, venue: TradingVenue, symbol: str
) -> AccountControlCleared | AccountControlRefused:
    """@return The venue's control when a change to `symbol` may be sent,
    the first failed check otherwise."""
    if not venue.supports_order_submission:
        return AccountControlRefused(ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED)
    scope = scopes.get(venue)
    control = scope.ports.account_control
    if control is None:
        return AccountControlRefused(AccountControlRefusal.NOT_A_FUTURES_VENUE)
    if not scope.session_state.enabled:
        return AccountControlRefused(ExecuteOrderSafetyGate.TRADING_SWITCH_OFF)
    holder = scope.session_state.lease_holder(symbol)
    if holder is not None:
        return AccountControlRefused(
            ExecuteOrderSafetyGate.SYMBOL_LEASED, f"{symbol} is managed by {holder}"
        )
    status = scope.ports.account_reader.check_connection()
    if not status.reachable or status.failure is not None:
        return AccountControlRefused(ExecuteOrderSafetyGate.CONNECTION_NOT_READY)
    try:
        position = control.open_position(symbol)
    except AccountControlRejectedError as refusal:
        return AccountControlRefused(
            AccountControlRefusal.EXCHANGE_REJECTED, str(refusal)
        )
    if position != 0:
        return AccountControlRefused(
            AccountControlRefusal.POSITION_OPEN,
            f"{symbol} has an open position of {position}",
        )
    return AccountControlCleared(control)
