"""`EPIC-010` — the address of one piece of remembered UI state.

`Lifetime` and `StateScope` live in the same file deliberately: a scope cannot
be described without its lifetime, and neither is meaningful alone. That is
Single-Scope Cohesion (`code-quality-rule.md` §7), not a violation of
Abstraction-Level Separation — they are one concept with two fields.

@par Why this is a value object and not a plain string key
The first design keyed every slice by route name, which silently assumes one
presenter instance per route. `PresenterManager` makes that true *today*
(one `presenter_instance` per registered route), but the moment anything can
produce a second live copy of the same screen — tabs, a second window, split
panes — that assumption breaks and every copy writes over the others.

Adding identity to a bare string key **later** would rewrite every stored key
and every call site. Adding it **now** costs one optional field that every
caller currently leaves as `None`. The asymmetry is the whole reason this type
exists; see `EPIC-010`'s design §2.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum

#: A value that survives `json.dump` unchanged. Declaring it means failure
#: mode #4 ("a slice held a `datetime` and blew up on the shutdown path") is
#: caught by the type checker rather than by a human remembering.
type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)

#: What one contributor hands over, and gets back.
type StateData = Mapping[str, JsonValue]


class Lifetime(Enum):
    """How long a scope's data is meant to survive.

    @details The member decides *which store* holds it, which is why the
    distinction is on the scope rather than on the store: a contributor writes
    `capture_state()` once and never learns where its data went.
    """

    #: Outlives the process. Written to disk.
    PERSISTENT = "persistent"

    #: Dies with the process, and with the instance that owns it. Never
    #: reaches disk — see `EPIC-010`'s design §4.2. Nothing in the application
    #: requests this yet; it exists because the in-memory store is the test
    #: double regardless, so the member costs nothing and keeps the key shape
    #: complete.
    SESSION = "session"


@dataclass(frozen=True, slots=True)
class StateScope:
    """Identifies exactly one slice of remembered state.

    @param key Which owner this belongs to — a route name (`"dashboard"`) or a
        shell component (`"shell"`).
    @param instance_id `None` for a singleton owner, which is every owner in
        this application today. A value identifies one live copy among several.
        Deliberately an unconstrained `str`: identity may nest (window 2 → tab
        3 → panel A), so no code here may assume it is flat or separator-free.
    @param lifetime See `Lifetime`.
    """

    key: str
    instance_id: str | None = None
    lifetime: Lifetime = Lifetime.PERSISTENT

    @property
    def is_singleton(self) -> bool:
        """Whether this scope names the only copy of its owner."""
        return self.instance_id is None

    def as_default(self) -> StateScope:
        """The singleton scope a new instance of this owner seeds from.

        @details For a singleton this is the scope itself. For a per-instance
        scope it is the shared template — *"what a new copy looks like"* —
        which is why it is always `PERSISTENT`: a template that died with the
        process would seed nothing.
        """
        return replace(self, instance_id=None, lifetime=Lifetime.PERSISTENT)

    @property
    def storage_key(self) -> str:
        """The flat string this scope occupies in the store.

        @details `ConfigManager` merges sources with a shallow `dict.update`,
        so slices must be distinct top-level keys rather than a nested tree —
        a nested `state` object would be replaced wholesale by any later
        layer instead of merged. Singletons keep the bare key so the on-disk
        file stays readable, which is most of why the file lives in the repo
        at all.
        """
        if self.instance_id is None:
            return self.key
        return f"{self.key}#{self.instance_id}"
