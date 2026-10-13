"""Write the health line after each snapshot (`EPIC-038D`).

The hook `HealthCadence.add_after` runs once per published snapshot. It reads the
snapshot, adds the one thing the snapshot does not hold - the process's resident
memory - and logs the line through `log_health_line`, the only emitter of the format
(`EPIC-038G`): INFO, whatever the numbers say.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    log_health_line,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_health_line import (
    health_line_of,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_process_memory import (
    IProcessMemory,
)

#: The logger the format was specified on (`EPIC-038G`): the scan and the sanity test
#: read `App.Operations - INFO - [health]`.
logger = logging.getLogger("App.Operations")


class HealthLineLogger:
    def __init__(self, memory: IProcessMemory) -> None:
        self._memory = memory

    def __call__(self, snapshot: HealthSnapshot) -> None:
        log_health_line(logger, health_line_of(snapshot, self._memory.resident_mb()))
