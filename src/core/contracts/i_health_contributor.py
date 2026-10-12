"""One module's part of the host's health snapshot (`EPIC-038C`).

A bounded context that knows something an operator wants on a status page - the
bots' states, the user stream's age, a feed's last tick - hands the snapshot
publisher one `IHealthContributor`. The publisher knows none by name, so a new
section is one class and one declaration (decision D3); the snapshot file,
`status` and the health line gain it with no edit.

**A contributor never blocks and never raises.** The publisher cuts a slow one
off at a deadline and reports a raising one as `unavailable`, but neither is a
licence: a contributor answers from what it already holds (a recorder fed by
events, a file it can read in microseconds), never from a network call.

**What a section may hold.** Counts, ages, state names and ids. No credential, no
account balance, no profit or PnL, no listen key (a bearer credential for the
user-data stream): the file is read by anyone who can read the data
root, and a monitor may ship it elsewhere. The publisher refuses a section that
names such a key.

**Saying "I am not well".** A section may set the reserved key `status` to
`"degraded"` (with a `reason`): `status` then exits 11 for the host, exactly as it
does when a section is `unavailable`. The rule is the same for every contributor;
the Engine's health check is one user of it, not a special case.

@par Extension cases
  · a new section (a future module's feed) - one contributor and one
    declaration in its module; `HealthPublisher`, the sink and `status` are
    untouched;
  · a section that needs a slower source - a recorder fed by events (as
    `trading` does for the user stream) keeps `snapshot()` instant.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue

#: The reserved keys of a section (`status`, `reason`) and the two values that say
#: the host is not well. Vocabulary of the kernel, not of `operations`: every
#: module's contributor may set them, and a section that holds none is well.
STATUS_KEY = "status"
REASON_KEY = "reason"
#: Set by the publisher when a contributor did not answer or was refused.
UNAVAILABLE = "unavailable"
#: Set by a contributor that answered and is not well.
DEGRADED = "degraded"


class IHealthContributor(ABC):
    """A named section of the snapshot."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The section's key: a lowercase word, unique across contributors."""

    @abstractmethod
    def snapshot(self) -> Mapping[str, JsonValue]:
        """The section now: JSON-ready, instant, free of secrets."""


class IHealthContributors(ABC):
    """The contributors the shell collected, for the publisher to read."""

    @abstractmethod
    def contributors(self) -> tuple[IHealthContributor, ...]:
        """Every declared contributor, in a stable order."""
