"""A daily period in which only CRITICAL goes out at once."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, tzinfo


@dataclass(frozen=True, slots=True)
class QuietHours:
    """`start` to `end` in `zone`, wrapping midnight when `start > end`. A `zone` of `None` is the
    machine's own clock, by the OS's rules for that instant (daylight saving included): the
    machine's zone has no IANA key the standard library can read, so it is never looked up by
    name (`display_timezone_service.machine_local_time`).

    Equal ends mean no quiet period rather than a whole day: "always quiet"
    would mute everything below CRITICAL, which no owner means by an empty form.
    """

    start: time
    end: time
    zone: tzinfo | None = UTC

    def contains(self, at: datetime) -> bool:
        moment = at.astimezone() if self.zone is None else at.astimezone(self.zone)
        local = moment.time().replace(tzinfo=None)
        start, end = self.start.replace(tzinfo=None), self.end.replace(tzinfo=None)
        if start == end:
            return False
        if start < end:
            return start <= local < end
        return local >= start or local < end
