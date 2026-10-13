"""Pre-flight: every bot file in the store can be read by this build (`EPIC-038H`).

A file written by a newer build (a `schema_version` this code does not know), or
damaged on disk, is refused by the store and **left untouched** - the restore
service never rewrites it - so the host starts and the bot simply is not there.
For a person upgrading a server that is the quiet failure: the bot they expect to
resume does not exist. This check says so before the host serves, by file name and
reason. It is a WARN, not a FAIL: refusing to serve would take every other bot down
with one unreadable file, and the file is safe where it is.

The reason is the store's own sentence about the file (`unknown schema_version 2`,
`bad JSON`); it names no bot parameter and no credential.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckFinding,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore

CHECK_ID = "bot-files-readable"

_REMEDY = (
    "The file is left untouched and its bot is not loaded. Install the build that wrote "
    "it (a rollback), or copy the file out of state/bots/ if it is damaged; do not edit it."
)


class BotFilesReadableCheck(IPreflightCheck):
    check_id = CHECK_ID
    title = "Bot files can be read by this build"

    def __init__(self, store: IBotStore) -> None:
        self._store = store

    def run(self, scope: PreflightScope) -> CheckResult:
        reading = self._store.load_all()
        if not reading.refused:
            return CheckResult.single(
                self.check_id,
                self.title,
                CheckFinding(
                    "bot files",
                    CheckStatus.PASS,
                    f"{len(reading.bots)} bot file(s) read",
                ),
            )
        return CheckResult(
            self.check_id,
            self.title,
            tuple(
                CheckFinding(
                    refused.name,
                    CheckStatus.WARN,
                    f"cannot be read by this build: {refused.reason}",
                    _REMEDY,
                )
                for refused in reading.refused
            ),
        )
