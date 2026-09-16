"""One mechanism for "every member of this enum has a user-facing label".

@details Twelve places in `presentation/` had grown their own copy of the
same shape — a module-level `dict[SomeEnum, str]` plus a lookup — and the
copies had already drifted into three different behaviours for the same
mistake:

* `.get(member, "something generic")` — a member nobody wrote a line for
  shows a vague fallback, and nothing anywhere says a line is missing;
* `table[member]` — a `KeyError` at the moment of display, which for a
  CLI formatter means a traceback instead of a status report;
* nothing — the table simply had to be right.

That is not twelve style choices, it is twelve chances to add an enum
member and forget its text. One had already been taken:
`EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE` (the
`BUG-088` race — an Emergency Stop landing mid-reconciliation) had no
line, so the one situation where a user most needs to be told *why*
their click was refused showed "Không thể bật giao dịch." instead.

@par Completeness is checked at import, not at display
Constructing an `EnumLabels` verifies every member is covered and raises
if not. That turns "somebody adds a member and forgets the label" from a
silent wrong string in front of a user into a failure the app cannot
start with and the test suite reports on collection. Loud beats late,
especially where the label explains why an order was refused.

@par Deliberately no `get()` with a default
A default is exactly the escape hatch that let the gap above go
unnoticed. Callers that genuinely have a non-enum input (a value parsed
from JSON, say) should validate it into the enum first — that is a
different problem with a different answer.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import Enum
from typing import TypeVar

E = TypeVar("E", bound=Enum)


class EnumLabels(Mapping[E, str]):
    """@brief A total mapping from an enum's members to display strings.

    @details A `Mapping`, so existing call sites keep working unchanged
    (`labels[member]`, `member in labels`, iteration) — the difference is
    that reaching a missing member is impossible, because construction
    already refused it.
    """

    def __init__(self, enum_cls: type[E], labels: Mapping[E, str]) -> None:
        """
        @param enum_cls Passed explicitly rather than inferred from the
        first key: an empty table has no first key, and that is precisely
        the case worth catching.
        @raises ValueError If a member has no label, if a label is blank
        (a whitespace-only string renders as a mysteriously empty row),
        or if a key is not a member of `enum_cls` at all.
        """
        unknown = [key for key in labels if not isinstance(key, enum_cls)]
        if unknown:
            raise ValueError(
                f"{enum_cls.__name__} labels contain keys that are not members: "
                f"{unknown!r}"
            )
        missing = [member.name for member in enum_cls if member not in labels]
        if missing:
            raise ValueError(
                f"{enum_cls.__name__} is missing a label for: {', '.join(missing)}. "
                "Every member needs one — see enum_labels.py for why this is an "
                "error rather than a fallback."
            )
        blank = [member.name for member, text in labels.items() if not text.strip()]
        if blank:
            raise ValueError(
                f"{enum_cls.__name__} has blank labels for: {', '.join(blank)}."
            )
        self._enum_cls = enum_cls
        self._labels: dict[E, str] = dict(labels)

    @property
    def enum_cls(self) -> type[E]:
        """The enum this table covers — lets a test assert completeness
        without repeating the enum's name."""
        return self._enum_cls

    def __getitem__(self, member: E) -> str:
        return self._labels[member]

    def __iter__(self) -> Iterator[E]:
        return iter(self._labels)

    def __len__(self) -> int:
        return len(self._labels)
