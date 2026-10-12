"""Trading's section of the health snapshot (`EPIC-038C`): the user-data streams.

Per venue the stream's state and how long it has been in it. The headline,
`stream_down_s`, is how long the worst stream has been out of `connected`
(0 when every stream known is connected, `null` when none has reported): while
the user stream is down the app is blind to its resting orders' fills, so this is
the number a monitor alerts on. The stream publishes state *changes*, not each
message, so there is no "age of the last message" to report.

`skew_ms` is `null`: nothing in the app keeps a clock skew and a contributor may
not make the network call that measures one. The `run` host measures it on its
health interval and publishes it (`EPIC-038D`), and `preflight` measures it once.

No account, balance, key or order id appears here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.user_stream_recorder import (
    UserStreamRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamState,
)

SECTION_NAME = "trading"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TradingHealthContributor(IHealthContributor):
    def __init__(
        self,
        streams: UserStreamRecorder,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._streams = streams
        self._clock = clock

    @property
    def name(self) -> str:
        return SECTION_NAME

    def snapshot(self) -> Mapping[str, JsonValue]:
        now = self._clock()
        venues: dict[str, JsonValue] = {}
        down: list[int] = []
        for venue, reading in sorted(
            self._streams.readings().items(), key=lambda item: item[0].value
        ):
            age = max(0, int((now - reading.since).total_seconds()))
            venues[venue.value] = {"state": reading.state.value, "state_age_s": age}
            if reading.state is not UserStreamState.CONNECTED:
                down.append(age)
        return {
            "user_stream": venues,
            "stream_down_s": (max(down) if down else 0) if venues else None,
            "skew_ms": None,
        }
