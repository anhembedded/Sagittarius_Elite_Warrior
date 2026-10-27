"""`EPIC-047H` — the host's single-document files, as a bridge session watches them: the market data and the host's reads.

@details The host-facts file has been watched by the session itself since `EPIC-047C`; the files `EPIC-047H`
adds (`state/market-data.json`, `state/host-reads.json`) follow the same rules, so they share this class and
its payload: `{state, revision, age_s, problem, document}` under the kind's name, in the snapshot and in an
event whenever the file's revision or liveness changes. The bridge decodes nothing here and calls no
exchange: a view reads a file the host wrote.

A kind's change is a new `(revision, state)`. The market file is written once a second, so a subscribed
desktop hears about one event a second per kind at most, and a quiet host sends only its heartbeat's
revision.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsLook,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_facts import (
    IBridgeFacts,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

#: The kind of the host-facts file, the one the protocol has carried since `EPIC-047C` (the snapshot's `facts`).
FACTS_KIND = "facts"

type LookKey = tuple[int, str]


def look_key(look: FactsLook) -> LookKey:
    return (look.revision, look.state.value)


def look_payload(roots: WireRoots, look: FactsLook) -> dict[str, object]:
    """One look as the protocol puts it: the document under its root's name, and what is known about its age."""
    document = (
        None
        if look.document is None
        else roots.encode(look.document.root, look.document.value)
    )
    return {
        "state": look.state.value,
        "revision": look.revision,
        "age_s": look.age_s,
        "problem": look.problem,
        "document": document,
    }


class DocumentWatch:
    def __init__(self, views: Mapping[str, IBridgeFacts], roots: WireRoots) -> None:
        self._views = dict(views)
        self._roots = roots
        self._seen: dict[str, LookKey] = {}

    def snapshot(self) -> dict[str, object]:
        """Every kind's payload now; what was sent is what later looks are compared with."""
        payloads: dict[str, object] = {}
        for kind, view in self._views.items():
            look = view.look()
            self._seen[kind] = look_key(look)
            payloads[kind] = look_payload(self._roots, look)
        return payloads

    def changes(self) -> list[tuple[str, dict[str, object]]]:
        """The kinds whose file moved since the last look, with their payloads."""
        moved: list[tuple[str, dict[str, object]]] = []
        for kind, view in self._views.items():
            look = view.look()
            if look_key(look) != self._seen.get(kind):
                self._seen[kind] = look_key(look)
                moved.append((kind, look_payload(self._roots, look)))
        return moved
