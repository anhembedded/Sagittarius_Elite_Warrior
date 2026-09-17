"""One editable parameter, and the group it belongs to — the Published
Language between a module that owns a parameterised thing (today,
`strategy`'s `BaseStrategy.inputs`) and a support package that renders a
form for it (`support/ui_kit`'s param-form widgets).

Lives here, in neither side: `support/ui_kit` may import `core` but no
module, not even through a `contracts/` package, and a module's
`contracts/` package may not import `support/ui_kit` — that exemption
covers a module's own `ui/` sub-package only (`architecture-rule.md` §3,
`boundaries/rules.py`). `core/contracts` is where both sides already meet
(`nav_metadata.py`, this same epic).

`ParamKind` is a translation of `support/indicators/scripting.InputKind`,
not an alias — `core` imports nothing but `core`, so the mapping happens
once, inside the publishing module's own adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ParamKind(Enum):
    """What kind of value one parameter holds, and so which widget renders
    it. Mirrors `support/indicators/scripting.InputKind` member-for-member;
    a new member there needs a new one here in the same commit. A `STRING`
    field with `options` set renders as a choice — there is no separate
    kind for it, matching the source enum exactly."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"


@dataclass(frozen=True, slots=True)
class ParamField:
    """One parameter's declared shape and its current value, together —
    the render and the edit are the same row, so they are the same type."""

    name: str
    label: str
    kind: ParamKind
    default: object
    value: object
    minval: float | None = None
    maxval: float | None = None
    options: tuple[str, ...] = ()
    suffix: str = ""
    step: float | None = None


@dataclass(frozen=True, slots=True)
class ParamGroup:
    """One labelled section of a parameter form, in declaration order."""

    label: str
    fields: tuple[ParamField, ...]
