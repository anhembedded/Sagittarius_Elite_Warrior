"""`IDeliveryFollowUp` — what the worker asks of the hub when a channel misbehaves.

The worker knows channels and the outbox; deciding *who else to tell* is the hub's
(it holds the routes). This is the one narrow door between them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IDeliveryFollowUp(ABC):
    @abstractmethod
    def channel_failing(self, channel_id: str, reason: str) -> None:
        """`channel_id` ran out of attempts or was refused: tell the owner through
        the channels still alive. `reason` carries no secret."""

    @abstractmethod
    def fail_over(self, alert_id: int, failed_channel_id: str) -> bool:
        """Queue the CRITICAL alert `alert_id` on another enabled channel that
        does not already hold it. `False` when none is left."""
