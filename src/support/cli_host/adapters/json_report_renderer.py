"""A report as one JSON document a script can parse."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_report_renderer import (
    IReportRenderer,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JsonReportRenderer(IReportRenderer):
    """`{"schema": "sew.<command>/<n>", "generated_at": "...Z", "data": {...}}`.

    The envelope is the same for every command, so a monitor reads `schema`
    first and `data` second. `generated_at` is when the report was rendered,
    in UTC; the clock is injected so a test can pin it. The layout is ignored:
    it is for people.
    """

    def __init__(self, clock: Callable[[], datetime] = _utc_now) -> None:
        self._clock = clock

    def render(self, report: Report) -> str:
        generated_at = (
            self._clock().astimezone(UTC).isoformat(timespec="seconds")
        ).replace("+00:00", "Z")
        envelope = {
            "schema": report.schema,
            "generated_at": generated_at,
            "data": report.payload,
        }
        return json.dumps(envelope, ensure_ascii=False, indent=2)
