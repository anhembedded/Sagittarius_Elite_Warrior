"""Ask one contributor for its section, within a deadline, and trust nothing it says (`EPIC-038C`).

A contributor "never blocks and never raises" (`IHealthContributor`) - and this
is what makes the promise safe to rely on. A snapshot that waited on a stuck
contributor would stop being written, and `status` would call a healthy host
stale, so each question is asked on a daemon thread and given up on at the
deadline; a contributor that raises, answers something JSON cannot hold, or
names a key that is a secret or a balance is reported `unavailable` with a
reason that is the *kind* of failure, never its text (an exception's message is
the one place a credential could leak from). The detail goes to the log.

A thread that outlives its deadline cannot be killed; it is remembered, and that
contributor is not asked again until it has finished, so a hung contributor
costs one thread, not one per interval.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    DEGRADED,
    STATUS_KEY,
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    unavailable_section,
)

logger = logging.getLogger("App.Operations.Health")

#: A section holding a key with one of these in its name is refused: the file
#: is readable by anyone who can read the data root.
FORBIDDEN_KEY_PARTS = (
    "secret",
    "password",
    "passphrase",
    "api_key",
    "apikey",
    "private_key",
    "token",
    "credential",
    "balance",
    "equity",
    "profit",
    "pnl",
    "listenkey",
    "listen_key",
)


class _Answer:
    """What the question thread leaves behind."""

    def __init__(self) -> None:
        self.section: Mapping[str, JsonValue] | None = None
        self.failure: BaseException | None = None


class HealthSectionCollector:
    """Asks contributors, one at a time, for their sections."""

    def __init__(self, deadline_s: float) -> None:
        self._deadline_s = deadline_s
        self._unanswered: dict[str, threading.Thread] = {}

    def collect(self, contributor: IHealthContributor) -> Mapping[str, JsonValue]:
        name = contributor.name
        earlier = self._unanswered.get(name)
        if earlier is not None and earlier.is_alive():
            return unavailable_section("still running an earlier question")
        self._unanswered.pop(name, None)
        answer = _Answer()
        thread = threading.Thread(
            target=self._ask,
            args=(contributor, answer),
            name=f"HealthSection-{name}",
            daemon=True,
        )
        thread.start()
        thread.join(self._deadline_s)
        if thread.is_alive():
            self._unanswered[name] = thread
            logger.warning(
                "[health-section] %r gave no answer within %ss", name, self._deadline_s
            )
            return unavailable_section(f"no answer within {self._deadline_s:g}s")
        return self._judged(name, answer)

    @staticmethod
    def _ask(contributor: IHealthContributor, answer: _Answer) -> None:
        try:
            answer.section = contributor.snapshot()
        except Exception as failure:  # noqa: BLE001 - the seam: a contributor's failure becomes its section
            answer.failure = failure

    def _judged(self, name: str, answer: _Answer) -> Mapping[str, JsonValue]:
        if answer.failure is not None:
            logger.warning(
                "[health-section] %r raised %s: %s",
                name,
                type(answer.failure).__name__,
                answer.failure,
            )
            return unavailable_section(f"raised {type(answer.failure).__name__}")
        section = answer.section
        if section is None:
            return unavailable_section("gave no section")
        claimed = section.get(STATUS_KEY)
        if claimed is not None and claimed != DEGRADED:
            # The reserved key: a contributor may say it is degraded and nothing
            # else. `unavailable` is the publisher's word, and a typo would
            # otherwise read as a well section.
            logger.warning(
                "[health-section] %r refused: status %r is not allowed", name, claimed
            )
            return unavailable_section("refused: reserved status key misused")
        forbidden = _forbidden_key_in(section)
        if forbidden is not None:
            logger.warning(
                "[health-section] %r refused: it holds the key %r", name, forbidden
            )
            return unavailable_section("refused: holds a secret or balance key")
        try:
            json.dumps(section)
        except (TypeError, ValueError):
            logger.warning("[health-section] %r refused: not JSON-ready", name)
            return unavailable_section("refused: not JSON-ready")
        return section


def _forbidden_key_in(value: object) -> str | None:
    if isinstance(value, Mapping):
        for key, inner in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                return str(key)
            found = _forbidden_key_in(inner)
            if found is not None:
                return found
    elif isinstance(value, list | tuple):
        for item in value:
            found = _forbidden_key_in(item)
            if found is not None:
                return found
    return None
