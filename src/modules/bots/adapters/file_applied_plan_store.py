"""The applied plan as a JSON file in the data root's state (`EPIC-038I`).

Written by write-temp-then-rename, so a reader (the `run` host, `status`) sees the old
record or the new one and never half of one. Read strictly: a record this build cannot
read is refused with a sentence that names the problem and **none of the content** - the
file is not meant to hold a secret, but a refusal that echoed it would leak one that got
in.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    AppliedPlanUnreadableError,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)

RECORD_SCHEMA = "sew.bot-plan-record/1"
_BOT_FIELDS = ("bot_id", "name", "venue", "desired_state")


class FileAppliedPlanStore(IAppliedPlanStore):
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> AppliedPlan | None:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as exc:
            raise AppliedPlanUnreadableError(
                f"the applied-plan record {self._path.name} cannot be read ({type(exc).__name__})"
            ) from None
        return _parse(text, self._path.name)

    def write(self, plan: AppliedPlan) -> None:
        document = {
            "schema": RECORD_SCHEMA,
            "bots": [
                {
                    "bot_id": bot.bot_id,
                    "name": bot.name,
                    "venue": bot.venue,
                    "desired_state": bot.desired_state.value,
                }
                for bot in plan.bots
            ],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        temporary.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self._path)


def _parse(text: str, file_name: str) -> AppliedPlan:
    def refuse(why: str) -> AppliedPlanUnreadableError:
        return AppliedPlanUnreadableError(
            f"the applied-plan record {file_name} is not one this build reads: {why}; "
            "apply the plan again to replace it"
        )

    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        raise refuse("it is not valid JSON") from None
    if not isinstance(raw, dict) or set(raw) != {"schema", "bots"}:
        raise refuse("it is not an object of schema and bots")
    if raw["schema"] != RECORD_SCHEMA or not isinstance(raw["bots"], list):
        raise refuse("its schema or its bots are not what this build writes")
    bots: list[AppliedBot] = []
    for entry in raw["bots"]:
        if not isinstance(entry, dict) or set(entry) != set(_BOT_FIELDS):
            raise refuse("a bot entry does not have exactly its four fields")
        if not all(isinstance(entry[name], str) for name in _BOT_FIELDS):
            raise refuse("a bot entry holds something that is not text")
        try:
            desired = DesiredState(entry["desired_state"])
        except ValueError:
            raise refuse("a desired state is neither running nor stopped") from None
        bots.append(AppliedBot(entry["bot_id"], entry["name"], entry["venue"], desired))
    return AppliedPlan(tuple(bots))
