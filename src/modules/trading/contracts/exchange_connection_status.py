"""`EPIC-021D` — the outcome of one read-only exchange connection check.

@details `ConnectionFailureKind`/`PositionMode`/`MarginType` live in the
same file as `ExchangeConnectionStatus` rather than one file each: unlike
`MarketDataVenue`/`TradingVenue` (`EPIC-021A`, separate files because each
carries its own ADR-level governance concern), these three are plain
implementation details of one result type, with no independent lifecycle —
splitting them would scatter one cohesive contract across four files for no
reader's benefit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

if TYPE_CHECKING:
    # Type-only: `account_summary.py` names `PositionMode` from this module,
    # so a runtime import in both directions would be a cycle.
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
        AccountSummary,
    )


class ConnectionFailureKind(str, Enum):
    """Named, UI-branchable reasons a connection check did not succeed —
    never a raw exchange error string (`EPIC-021D` §2.2: "một chuỗi tiếng
    Anh của sàn không phải hợp đồng ổn định")."""

    #: No credentials configured — `IExchangeCredentialsProvider.resolve()`
    #: returned `CredentialsSource.NONE`. No network call was attempted.
    NOT_CONFIGURED = "not_configured"
    #: Binance `-1022` — the request's signature does not verify. Usually a
    #: mismatched/corrupted API secret.
    BAD_SIGNATURE = "bad_signature"
    #: Binance `-1021` — local clock too far from server time for the
    #: request's `recvWindow`.
    CLOCK_SKEW = "clock_skew"
    #: Binance `-2015` — invalid API key, wrong IP allowlist, or
    #: insufficient permissions. Named for the single most common real
    #: cause (a Spot Testnet or mainnet key used here by mistake — those
    #: keys are simply invalid for Futures Testnet, not "expired" in the
    #: literal sense), matching this task's own design.
    KEY_EXPIRED = "key_expired"
    #: Could not reach the exchange at all — DNS/TCP/TLS failure, timeout,
    #: or any Binance error code not covered by a more specific kind above.
    NETWORK = "network"
    #: `EPIC-021D` §2.3 — added beyond the plan's original 5-member list.
    #: The account's position mode is Hedge, not One-way; the whole epic's
    #: order model assumes One-way (ADR §6), so this is a distinct, named,
    #: blocking failure — not a warning alongside an otherwise-successful
    #: connection, and not silently folded into one of the 5 kinds above
    #: (none of which mean "connected fine, but this account can't trade
    #: here").
    HEDGE_MODE_UNSUPPORTED = "hedge_mode_unsupported"


class PositionMode(str, Enum):
    ONE_WAY = "one_way"
    HEDGE = "hedge"


class MarginType(str, Enum):
    CROSSED = "crossed"
    ISOLATED = "isolated"


@dataclass(frozen=True)
class ExchangeConnectionStatus:
    """Immutable result of one `GetExchangeConnectionStatusQuery`.

    @details Every field beyond `venue`/`reachable`/`failure` is `None`
    when it was never learned — either the check failed before reaching
    that data, or (for `margin_type`) the account has no open position to
    infer it from (margin type is per-symbol on Binance Futures, not
    account-wide; see `FuturesAccountReader`'s own docstring). `holdings`/
    `equity` are the symmetric case (`EPIC-027H`): Spot concepts a Futures
    venue answers `None` for, same as `position_mode`/`margin_type` answer
    `None` for Spot — see `i_account_snapshot.py`'s own "@par The seam".

    `summary` (`EPIC-028D`) is what a desk shows about the account, read
    from the same account payload as everything above, so asking for it
    costs no second request. `None` unless the check got far enough to read
    the account (and, on Futures, its position mode).
    """

    venue: TradingVenue
    reachable: bool
    failure: ConnectionFailureKind | None
    server_time_skew_ms: int | None
    usdt_balance: Decimal | None
    position_mode: PositionMode | None
    margin_type: MarginType | None
    open_position_count: int | None
    holdings: tuple[SpotHolding, ...] | None = None
    equity: Decimal | None = None
    summary: AccountSummary | None = None
