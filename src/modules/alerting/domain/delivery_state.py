"""Where one alert's trip through one channel stands."""

from __future__ import annotations

from enum import Enum


class DeliveryState(Enum):
    PENDING = "pending"
    RETRYING = "retrying"
    SENT = "sent"
    FAILED = "failed"
    EXPIRED = "expired"
    DROPPED = "dropped"

    @property
    def is_open(self) -> bool:
        """Still to be attempted."""
        return self in (DeliveryState.PENDING, DeliveryState.RETRYING)
