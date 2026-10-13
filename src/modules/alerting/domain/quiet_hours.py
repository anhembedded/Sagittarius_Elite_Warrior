"""A daily period in which only CRITICAL goes out at once."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, tzinfo


@dataclass(frozen=True, slots=True)
class QuietHours:
    """`start` to `end` in `zone`, wrapping midnight when `start > end`.

    Equal ends mean no quiet period rather than a whole day: "always quiet"
    would mute everything below CRITICAL, which no owner means by an empty form.
    """

    start: time
    end: time
    zone: tzinfo = UTC

    def contains(self, at: datetime) -> bool:
        local = at.astimezone(self.zone).time().replace(tzinfo=None)
        start, end = self.start.replace(tzinfo=None), self.end.replace(tzinfo=None)
        if start == end:
            return False
        if start < end:
            return start <= local < end
        return local >= start or local < end
