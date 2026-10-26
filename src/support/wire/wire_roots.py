"""`EPIC-047A` — the closed list of types that may cross the remote link, each under its wire name.

Only a root named here, and the records reachable from it, can be encoded or decoded: a
message naming anything else is refused. That is how no secret, key or unfiltered exception
text reaches the wire by accident. The list is closed twice: at the door (an unnamed root is
an `unknown wire name`) and at registration (`WireRoots` refuses a graph holding a field
named like a secret, or a type with no wire form, before any message flows).

A message is `{"schema": <root wire name>, "data": …}`, with `"revision"` when the sender
numbers its changes (`RevisionGate` is the receiver's side).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.support.wire.wire_codec import decode, encode
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import (
    WireDecodeError,
    WireSchemaError,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_schema import (
    combined_hash,
    hash_of_schema,
    schema_of,
    union_member_names,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_shape import (
    EnumShape,
    FixedTupleShape,
    ItemsShape,
    MappingShape,
    OptionalShape,
    RecordShape,
    ScalarShape,
    Shape,
    UnionShape,
    shape_of,
)

SCHEMA_KEY = "schema"
DATA_KEY = "data"
REVISION_KEY = "revision"

_ROOT_NAME = re.compile(r"sew\.[a-z0-9]+(?:-[a-z0-9]+)*/[0-9]+")
#: A field named like one of these never crosses the link; a key is not a fact the desktop reads.
_SECRET_FIELD = re.compile(
    r"secret|password|passphrase|private_?key|api_?key|token|credential", re.IGNORECASE
)


class WireRoots:
    """The registry: encodes a value under its root's name, decodes a message by the name it carries."""

    def __init__(self, roots: Iterable[WireRoot]) -> None:
        self._roots: dict[str, WireRoot] = {}
        for root in roots:
            if _ROOT_NAME.fullmatch(root.name) is None:
                raise WireSchemaError(
                    f"a root's wire name reads 'sew.some-words/1', not {root.name!r}"
                )
            if root.name in self._roots:
                raise WireSchemaError(f"two roots share the wire name {root.name}")
            _refuse_secrets(root, shape_of(root.hint), set())
            self._roots[root.name] = root

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._roots))

    def root_hashes(self) -> dict[str, str]:
        """One digest per root, over its wire name and the schema of its wire form."""
        return {
            n: hash_of_schema(n, schema_of(r.hint))
            for n, r in sorted(self._roots.items())
        }

    def contract_hash(self) -> str:
        """One digest over every root's: equal on two builds exactly when their wire forms are."""
        return combined_hash(self.root_hashes())

    def wire_names(self) -> tuple[str, ...]:
        """Every wire name this build carries: the roots and the members of every union."""
        names = set(self._roots)
        for root in self._roots.values():
            names |= union_member_names(root.hint)
        return tuple(sorted(names))

    def hint_of(self, name: str) -> object:
        return self._root(name, WireSchemaError).hint

    def encode(
        self, name: str, value: object, *, revision: int | None = None
    ) -> dict[str, object]:
        doc: dict[str, object] = {
            SCHEMA_KEY: name,
            DATA_KEY: encode(value, self._root(name, WireSchemaError).hint),
        }
        if revision is not None:
            doc[REVISION_KEY] = revision
        return doc

    def decode(self, doc: object) -> object:
        name = self.schema_of(doc)
        return decode(doc[DATA_KEY], self._root(name, WireDecodeError).hint)  # type: ignore[index]

    def schema_of(self, doc: object) -> str:
        """The wire name a message carries, checked to be a message of this build's list."""
        if type(doc) is not dict or SCHEMA_KEY not in doc or DATA_KEY not in doc:
            raise WireDecodeError(
                f"a message is an object with {SCHEMA_KEY!r} and {DATA_KEY!r}"
            )
        extra = sorted(doc.keys() - {SCHEMA_KEY, DATA_KEY, REVISION_KEY})
        if extra:
            raise WireDecodeError(f"a message has no field {', '.join(extra)}")
        name = doc[SCHEMA_KEY]
        if type(name) is not str or name not in self._roots:
            raise WireDecodeError(
                f"unknown wire name {name!r}; this build knows {', '.join(self.names)}"
            )
        return name

    def _root(
        self, name: str, error: type[WireSchemaError | WireDecodeError]
    ) -> WireRoot:
        root = self._roots.get(name)
        if root is None:
            raise error(
                f"unknown wire name {name!r}; this build knows {', '.join(self.names)}"
            )
        return root


def revision_of(doc: object) -> int | None:
    """The revision a message carries, `None` when the sender did not number it."""
    if type(doc) is not dict:
        raise WireDecodeError("a message is an object")
    revision = doc.get(REVISION_KEY)
    if revision is None:
        return None
    if type(revision) is not int or revision < 0:
        raise WireDecodeError(f"a revision is a whole number from 0, not {revision!r}")
    return revision


def _refuse_secrets(root: WireRoot, shape: Shape, seen: set[type]) -> None:
    match shape:
        case RecordShape(cls, fields):
            _refuse_secret_fields(root, cls, fields, seen)
        case OptionalShape(inner) | ItemsShape(inner) | MappingShape(inner):
            _refuse_secrets(root, shape_of(inner), seen)
        case FixedTupleShape(items):
            for item in items:
                _refuse_secrets(root, shape_of(item), seen)
        case UnionShape(members):
            for _, cls in members:
                _refuse_secrets(root, shape_of(cls), seen)
        case ScalarShape() | EnumShape():
            return


def _refuse_secret_fields(
    root: WireRoot, cls: type, fields: tuple[tuple[str, object], ...], seen: set[type]
) -> None:
    if cls in seen:
        return
    seen.add(cls)
    for name, hint in fields:
        if _SECRET_FIELD.search(name):
            raise WireSchemaError(
                f"{root.name}: {cls.__qualname__}.{name} is named like a secret; "
                "a key or a credential never crosses the link"
            )
        _refuse_secrets(root, shape_of(hint), seen)
