"""`EPIC-028F` — the outcome of a leverage or margin-mode change."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)


class AccountControlRefusal(str, Enum):
    """Why a change was not applied, beyond the order path's safety gates."""

    #: The venue has no leverage or margin mode (Spot). Refused before any
    #: request.
    NOT_A_FUTURES_VENUE = "not_a_futures_venue"
    #: The symbol has an open position; Binance refuses both changes then,
    #: and the app says so before asking.
    POSITION_OPEN = "position_open"
    #: The exchange answered and refused; `detail` carries its code and
    #: message.
    EXCHANGE_REJECTED = "exchange_rejected"
    #: Another copy of the app holds the data root; this one changes nothing
    #: (`EPIC-035H`). `detail` is the instance's own reason.
    READ_ONLY_INSTANCE = "read_only_instance"


@dataclass(frozen=True)
class AccountControlResult[T]:
    """@details `applied` is what the exchange confirmed (a
    `LeverageSetting`, or the `MarginType` now in effect) and is `None`
    exactly when `blocked_by` is set. The safety gates are the order path's
    own (`ExecuteOrderSafetyGate`): changing leverage is signed account
    activity, gated like a cancel."""

    blocked_by: ExecuteOrderSafetyGate | AccountControlRefusal | None
    applied: T | None
    #: A human-readable reason for a refusal: the open position, or the
    #: exchange's own code and message.
    detail: str | None = None

    def __post_init__(self) -> None:
        if (self.blocked_by is None) == (self.applied is None):
            raise ValueError(
                "exactly one of blocked_by and applied is set: "
                f"blocked_by={self.blocked_by}, applied={self.applied}"
            )

    @property
    def blocked(self) -> bool:
        return self.blocked_by is not None
