"""A log call's message template: fixed text pieces with a typed hole between each pair.

A `%`-template `"Bot %s: exit slice %d of %s"` is pieces `("Bot ", ": exit slice ",
" of ", "")` and kinds `("s", "d", "s")`; an f-string is the same with kind `h` for
each `{...}`. `compile_first_line` turns it into the regular expression that finds
the holes in the first line of a record's message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: `s` text (`%s %r %a %c`), `d` integer, `f` real, `x` other number base, `h` f-string hole.
HOLE_KINDS = frozenset("sdfxh")
_HOLE_PATTERNS = {
    "s": r"(.*?)",
    "h": r"(.*?)",
    "d": r"(-?\d+)",
    "f": r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|nan|inf)",
    "x": r"(\S+?)",
}
#: A template with fewer fixed non-blank characters than this (`"%s: %s"`) would match
#: any line, so it is left to the heuristic.
MIN_FIXED_CHARACTERS = 4


@dataclass(frozen=True, slots=True)
class LogTemplate:
    pieces: tuple[str, ...]
    kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.pieces) != len(self.kinds) + 1 or not set(self.kinds) <= HOLE_KINDS:
            raise ValueError(f"malformed log template: {self.pieces!r} {self.kinds!r}")

    @property
    def fixed_characters(self) -> int:
        """How many non-blank characters of the message are fixed text."""
        return sum(1 for ch in "".join(self.pieces) if not ch.isspace())

    @property
    def anchor(self) -> str:
        """The longest fixed piece, which a line must contain to be worth a regex run."""
        return max((piece.strip() for piece in self.pieces), key=len)

    def is_specific_enough(self) -> bool:
        return self.fixed_characters >= MIN_FIXED_CHARACTERS


def compile_first_line(template: LogTemplate) -> re.Pattern[str]:
    """The expression for the record's first line: the template cut at its first newline.

    A line is read on its own, so a template whose fixed text holds a newline
    (`"... detail:\\n%s"`) is matched up to that newline."""
    pieces = list(template.pieces)
    kinds = list(template.kinds)
    for position, piece in enumerate(pieces):
        if "\n" in piece:
            pieces = [*pieces[:position], piece.split("\n", 1)[0]]
            kinds = kinds[:position]
            break
    parts = [re.escape(pieces[0])]
    for kind, piece in zip(kinds, pieces[1:], strict=True):
        parts.append(_HOLE_PATTERNS[kind])
        parts.append(re.escape(piece))
    return re.compile("".join(parts), re.DOTALL)
