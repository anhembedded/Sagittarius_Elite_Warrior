"""Find which words of a plain message a log call substituted, from the call's template.

Each template is a regular expression over the first line of the message; a line is
tried only against the templates whose longest fixed piece it contains. The best
match is the one with the most fixed text. When two templates fit equally well and
disagree on the holes, nothing is claimed (the caller then guesses): a wrong exact
answer is worse than an honest guess.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.log_view.template_model import (
    LogTemplate,
    compile_first_line,
)


@dataclass(frozen=True, slots=True)
class _Entry:
    template: LogTemplate
    pattern: re.Pattern[str]


class TemplateMatcher:
    def __init__(self, templates: tuple[LogTemplate, ...]) -> None:
        by_anchor: dict[str, list[_Entry]] = defaultdict(list)
        for template in templates:
            by_anchor[template.anchor].append(
                _Entry(template, compile_first_line(template))
            )
        self._by_anchor = dict(by_anchor)

    def __len__(self) -> int:
        return sum(len(entries) for entries in self._by_anchor.values())

    def values_in(self, message: str) -> tuple[tuple[int, int], ...] | None:
        """The (start, end) of each non-empty hole, or `None` when no template fits
        or the best ones disagree."""
        best_fixed = -1
        best: list[tuple[tuple[int, int], ...]] = []
        for anchor, entries in self._by_anchor.items():
            if anchor not in message:
                continue
            for entry in entries:
                found = entry.pattern.fullmatch(message)
                if found is None:
                    continue
                fixed = entry.template.fixed_characters
                if fixed < best_fixed:
                    continue
                if fixed > best_fixed:
                    best_fixed, best = fixed, []
                best.append(_holes(found))
        if not best or any(other != best[0] for other in best[1:]):
            return None
        return best[0]


def _holes(found: re.Match[str]) -> tuple[tuple[int, int], ...]:
    return tuple(
        found.span(group)
        for group in range(1, (found.re.groups or 0) + 1)
        if found.end(group) > found.start(group)
    )
