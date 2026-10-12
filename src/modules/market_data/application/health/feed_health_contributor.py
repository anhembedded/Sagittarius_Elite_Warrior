"""Market data's section of the health snapshot (`EPIC-038C`): how fresh each feed is.

`tick_age_s` is the age of the freshest candle across every feed (the health
line's field): `null` when no feed has delivered one, which is the normal state
of a host that has opened none. `feeds` gives each `market:symbol` its own age.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.market_data.application.health.last_tick_recorder import (
    LastTickRecorder,
)

SECTION_NAME = "market_data"


class FeedHealthContributor(IHealthContributor):
    def __init__(self, ticks: LastTickRecorder) -> None:
        self._ticks = ticks

    @property
    def name(self) -> str:
        return SECTION_NAME

    def snapshot(self) -> Mapping[str, JsonValue]:
        ages = self._ticks.ages_s()
        feeds: dict[str, JsonValue] = {key: age for key, age in ages.items()}
        return {"tick_age_s": min(ages.values()) if ages else None, "feeds": feeds}
