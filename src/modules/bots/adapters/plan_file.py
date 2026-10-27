"""`BOT-176` — the one writer of a plan file, shared by `bot export` and the desktop's Export plan….

A plan is never written over another file: the create is exclusive, so the check and the
write are one step and a file made in between is still refused. The result is a value, not
an exception, so neither caller lets an `OSError` cross its boundary.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_plan_file_writer import (
    IPlanFileWriter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_file import (
    PlanFileRefused,
    PlanFileWritten,
)


class PlanFileWriter(IPlanFileWriter):
    def write_new(self, path: Path, text: str) -> PlanFileWritten | PlanFileRefused:
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(text)
        except FileExistsError:
            return PlanFileRefused(path, "exists")
        except OSError as failure:
            return PlanFileRefused(
                path, "os_error", failure.strerror or type(failure).__name__
            )
        return PlanFileWritten(path)
