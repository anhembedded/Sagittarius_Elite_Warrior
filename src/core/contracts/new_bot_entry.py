"""The bot a `bot add` asks the running host to create, in the shape that may cross the command file (`EPIC-045A`).

A plan file's entry (name, kind, venue, symbol, params) minus what a plan adds and an add must not
carry: `desired_state` (an add starts nothing). The command directory is a trust boundary, so every
field has a short closed shape, checked where the entry is built: a name of words, a kind and a
venue of lower-case words, an upper-case symbol and at most `MAX_SETTINGS_PER_EDIT` parameters, each
a `ParameterSetting`. Whether the kind exists, the venue is one this build trades on and the
parameters are readable is the host's answer, in words (`AddBotForHostCommandHandler`); the shape
only keeps what is not a bot out of the host.

The whole document is about 2 KB at the longest values, inside `MAX_COMMAND_BYTES`.

@par Extension cases
  · a name with a bracket or an accent - the name shape widens here and the codec follows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    MAX_SETTINGS_PER_EDIT,
    ParameterSetting,
)

_NAME_SHAPE = re.compile(
    r"^[A-Za-z0-9_.:+-]([A-Za-z0-9 _.:+-]{0,62}[A-Za-z0-9_.:+-])?$"
)
_KIND_SHAPE = re.compile(r"^[a-z0-9_]{1,32}$")
_VENUE_SHAPE = re.compile(r"^[a-z0-9_]{1,32}$")
_SYMBOL_SHAPE = re.compile(r"^[A-Z0-9]{1,32}$")


@dataclass(frozen=True, slots=True)
class NewBotEntry:
    """A bot to create, as text; `ParameterSetting` states the shape of each parameter.

    @raise ValueError A field is not the shape of one, or there are too many parameters or one
        twice; the message names the field and never repeats its value.
    """

    name: str
    kind: str
    venue: str
    symbol: str
    params: tuple[ParameterSetting, ...] = ()

    def __post_init__(self) -> None:
        if not _NAME_SHAPE.fullmatch(self.name):
            raise ValueError(
                "the name is 1-64 characters of letters, digits, spaces and _ . : + -, "
                "without a space at either end"
            )
        if not _KIND_SHAPE.fullmatch(self.kind):
            raise ValueError("the kind is 1-32 characters of a-z, 0-9 and _")
        if not _VENUE_SHAPE.fullmatch(self.venue):
            raise ValueError("the venue is 1-32 characters of a-z, 0-9 and _")
        if not _SYMBOL_SHAPE.fullmatch(self.symbol):
            raise ValueError("the symbol is 1-32 characters of A-Z and 0-9")
        if len(self.params) > MAX_SETTINGS_PER_EDIT:
            raise ValueError(
                f"a new bot takes at most {MAX_SETTINGS_PER_EDIT} parameters, not {len(self.params)}"
            )
        keys = [setting.key for setting in self.params]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        if repeated:
            raise ValueError(f"{', '.join(repeated)} is given more than once")
