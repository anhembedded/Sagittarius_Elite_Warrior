"""`EPIC-047E` — one host file as the bridge reported it: the document, how old it is and whether the host lives.

@details The bridge puts every host file in a snapshot and in an event as `{state, revision, age_s, problem,
document}` (`support/wire/bridge/bridge_documents.py`). The desktop keeps the latest of each kind with its
state, because "the host went quiet" and "there is no file" are different sentences on the screen, and a
document that is old is still the last data (decision record 2026-10-27, D5).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsState,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots


@dataclass(frozen=True, slots=True)
class DocumentLook:
    state: FactsState
    revision: int
    #: Seconds since the host wrote the file, by the bridge's clock on the host; `None` without a file.
    age_s: float | None
    problem: str
    #: The decoded document, or `None` when the host has published none.
    document: object | None


NO_DOCUMENT = DocumentLook(FactsState.MISSING, 0, None, "", None)


def look_of(roots: WireRoots, payload: object) -> DocumentLook:
    """The look in one bridge payload. A payload this build cannot read is a missing file with the reason."""
    if not isinstance(payload, dict):
        return DocumentLook(
            FactsState.MISSING, 0, None, "the host sent no such file", None
        )
    state = _state_of(payload.get("state"))
    revision = payload.get("revision")
    age = payload.get("age_s")
    problem = payload.get("problem")
    encoded = payload.get("document")
    document: object | None = None
    unreadable = ""
    if encoded is not None:
        try:
            document = roots.decode(encoded)
        except WireDecodeError as failure:
            unreadable = f"the host's file could not be read by this build: {failure}"
    return DocumentLook(
        state,
        revision if isinstance(revision, int) else 0,
        float(age) if isinstance(age, int | float) else None,
        unreadable or (problem if isinstance(problem, str) else ""),
        document,
    )


def _state_of(raw: object) -> FactsState:
    if not isinstance(raw, str):
        return FactsState.MISSING
    try:
        return FactsState(raw)
    except ValueError:
        return FactsState.MISSING
