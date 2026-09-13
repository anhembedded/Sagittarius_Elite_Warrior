"""The ratchet file: violations recorded as found, one per pair (HLD §6.1).

The identity of an entry is `(importing_module, imported_module)` with no line
number — ArchUnit's frozen-rule identity — so an unrelated edit to a file never
churns the list. Comments start with `#`; entries read `a -> b`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ARROW = "->"
_COMMENT = "#"


@dataclass(frozen=True, order=True)
class Violation:
    importing_module: str
    imported_module: str

    def as_line(self) -> str:
        return f"{self.importing_module} {_ARROW} {self.imported_module}"


def read_allowlist(path: Path) -> list[Violation]:
    entries: list[Violation] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split(_COMMENT, 1)[0].strip()
        if not line:
            continue
        importing, arrow, imported = line.partition(_ARROW)
        if not arrow:
            raise ValueError(
                f"malformed allowlist line (expected `a {_ARROW} b`): {raw!r}"
            )
        entries.append(Violation(importing.strip(), imported.strip()))
    return entries
