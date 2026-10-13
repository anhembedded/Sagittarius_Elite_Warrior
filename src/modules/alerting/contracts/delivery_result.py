"""What a channel answers after one try (`EPIC-036A`, design §6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """The platform accepted the message (`ok`), asked to wait (`retry_after`,
    a Discord 429), or will never accept it (`permanent`, a deleted webhook).

    `reason` is shown in the history and may be sent to another channel, so it
    names the failure and **never** carries a URL, a token or a response body.
    """

    ok: bool
    retry_after: timedelta | None = None
    permanent: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        if self.ok and (self.retry_after is not None or self.permanent):
            raise ValueError("An ok result carries no retry_after and is not permanent")
        if self.ok:
            return
        if not self.reason:
            raise ValueError("A failed result must say its reason")
        if self.retry_after is not None and self.retry_after <= timedelta(0):
            raise ValueError("retry_after must be positive")
        if self.permanent and self.retry_after is not None:
            raise ValueError(
                "A permanent failure is not retried, so has no retry_after"
            )

    @classmethod
    def sent(cls) -> DeliveryResult:
        return cls(ok=True)

    @classmethod
    def retry_later(cls, after: timedelta, reason: str) -> DeliveryResult:
        """The platform asked to wait `after` (a rate limit)."""
        return cls(ok=False, retry_after=after, reason=reason)

    @classmethod
    def failed(cls, reason: str) -> DeliveryResult:
        """A failure that may pass (a timeout, a 5xx): the worker backs off."""
        return cls(ok=False, reason=reason)

    @classmethod
    def refused(cls, reason: str) -> DeliveryResult:
        """A failure that will not pass without the owner (a deleted webhook)."""
        return cls(ok=False, permanent=True, reason=reason)
