"""Application port for a read-only exchange connection/account check
(`EPIC-021D`).

@details Deliberately not `ITradingClient` — that port (order placement) is
`EPIC-021E`'s, and does not exist yet. This one can never place, modify, or
cancel anything; its single method always returns, never raises — every
failure mode (no credentials, bad signature, clock skew, wrong key,
network, unsupported account mode) is a named value inside the result, not
an exception a caller must anticipate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ExchangeConnectionStatus,
)


class ITradingAccountReader(ABC):
    """Port for checking whether this app can talk to the trading venue,
    and what state that account is in."""

    @abstractmethod
    def check_connection(self) -> ExchangeConnectionStatus:
        """@brief Pings the trading venue, measures clock skew, and reads
        account balance/position mode/margin type — all read-only.
        @return An `ExchangeConnectionStatus` describing exactly how far
        the check got and why it stopped, if it did. Never raises.
        """
