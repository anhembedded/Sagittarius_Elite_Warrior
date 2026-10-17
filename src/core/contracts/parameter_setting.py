"""One `key=value` an operator sets on a bot, and the bounds of a set of them (`EPIC-038L`).

A bot's parameters are text (`BotDefinition.config` is `Mapping[str, str]`: the kind parses them,
`Decimal` for money, so no float touches a price), so a setting is text too and the verb never types
a value. Which keys exist and which values are readable is the bot kind's answer
(`IBotKind.parameter_problem`); what is fixed here is only the *shape* a setting must have to cross
the command file, which is a trust boundary: a short key of lower-case words and a short value
without whitespace, quotes or control characters.

@par Extension cases
  · a value that needs a space or a quote (a free-text parameter) - the value shape widens here, and
    the codec's size limit (`MAX_COMMAND_BYTES`) still bounds a document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: The most settings one `bot edit` carries. A Grid has ten parameters, so this is room, not a target;
#: with the longest key and value the document is about 2 KB, inside `MAX_COMMAND_BYTES`.
MAX_SETTINGS_PER_EDIT = 16

_KEY_SHAPE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_VALUE_SHAPE = re.compile(r"^[A-Za-z0-9_.:+-]{1,64}$")


@dataclass(frozen=True, slots=True)
class ParameterSetting:
    """A parameter's key and the text to store under it.

    @raise ValueError The key or the value is not the shape of one; the message names which and
        never repeats the value.
    """

    key: str
    value: str

    def __post_init__(self) -> None:
        if not _KEY_SHAPE.fullmatch(self.key):
            raise ValueError(
                "a parameter key is 1-32 characters of a-z, 0-9 and _, starting with a letter"
            )
        if not _VALUE_SHAPE.fullmatch(self.value):
            raise ValueError(
                f"the value of {self.key} is empty, longer than 64 characters or holds a character "
                "other than letters, digits and _ . : + -"
            )

    @classmethod
    def parse(cls, text: str) -> ParameterSetting:
        """`key=value`, split at the first `=`.

        @raise ValueError There is no `=`, or the key or the value is not the shape of one.
        """
        key, separator, value = text.partition("=")
        if not separator:
            raise ValueError("it is not key=value")
        return cls(key, value)
