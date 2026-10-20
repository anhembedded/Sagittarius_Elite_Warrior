"""`BOT-197` — who an order-session opening is for.

@details An opening names one of three things. A bot id (`str`): that bot's Start, Resume or
stop needed the session, and no other bot is woken by it. `OpenedByPerson.PERSON`: a person's
own action opened it (a manual order, arming a strategy), which belongs to no bot and so wakes
no bot waiting for its own Resume (ADR 038 O2: nothing resumes a bot except that bot's own
Resume or the host's `--resume-recovering`). `None`: no opener is known, the default of a
caller that has not said, which still wakes a waiting bot.
"""

from __future__ import annotations

from enum import Enum


class OpenedByPerson(Enum):
    """The opener is a person's action that belongs to no bot."""

    PERSON = "person"


#: A bot id, a person, or `None` (unknown). The one type every layer carries.
SessionOpener = str | OpenedByPerson | None
