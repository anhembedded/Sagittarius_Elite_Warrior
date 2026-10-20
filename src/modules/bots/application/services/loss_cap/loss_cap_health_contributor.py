"""The loss cap's section of the health snapshot (`EPIC-026L`).

What `status` and the host's health line show the owner about the cap: its figure, the day's
result, and whether it is tripped. It holds the figure and a sum of money, no bot name and no
credential. A cap that is off says so (`figure` is `null`): "off" is a state the owner must be
able to see, not the absence of a section.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_status import (
    ILossCapStatus,
)

SECTION_NAME = "loss_cap"


class LossCapHealthContributor(IHealthContributor):
    @property
    def name(self) -> str:
        return SECTION_NAME

    def __init__(self, status: ILossCapStatus) -> None:
        self._status = status

    def snapshot(self) -> Mapping[str, JsonValue]:
        return self._status.status().payload()
