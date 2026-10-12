"""What a report command produces, before anyone decides how it looks.

`EPIC-038B`. A command knows *what* it found; a renderer knows *how* to show it
(`i_report_renderer.py`). `Report` is the hand-over between the two: a
versioned, JSON-ready `payload` for machines and a neutral `layout` for
people. Because the command never builds a string, a second output format is a
second renderer, not a second copy of every command's printing code.

**The layout is not text.** It is sections of rows of cells; a cell may carry a
column width, which is a property of a table and not of any one renderer. A
renderer that has no use for it (JSON) ignores the whole layout.

**The payload is the contract with scripts.** Its keys are pinned per command
by a test: a field is added within a version, never renamed or removed; a
breaking change is a new `version`, which changes the `schema` string
(`sew.<command>/<version>`).

@par Extension cases
  · a new report command — build a `Report` and hand it to `emit_report`;
    no renderer and no parser changes;
  · a new payload field — add it and extend the pinned key set; the version
    stays;
  · a breaking payload change — bump `version`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

#: What JSON can hold. A payload that holds anything else (a `Decimal`, an
#: enum, a `datetime`) is a bug in the command, found by `json.dumps`.
type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


@dataclass(frozen=True, slots=True)
class ReportCell:
    """One piece of a row; `width` pads it when the row has a cell after it."""

    text: str
    width: int = 0


@dataclass(frozen=True, slots=True)
class ReportRow:
    cells: tuple[ReportCell, ...]

    @classmethod
    def of(cls, text: str) -> ReportRow:
        """A row that is a single unpadded cell."""
        return cls((ReportCell(text),))


@dataclass(frozen=True, slots=True)
class ReportSection:
    """A titled run of rows; `title` is `None` for an untitled one."""

    title: str | None
    rows: tuple[ReportRow, ...]


@dataclass(frozen=True, slots=True)
class Report:
    """The result of one report command."""

    #: The command word, as `cli_commands.json` spells it (`"exchange-status"`).
    command: str
    #: Bumped only by a breaking change to `payload`.
    version: int
    #: The machine-readable facts. Never a secret (a test greps for one).
    payload: Mapping[str, JsonValue]
    #: The human-readable form of the same facts.
    layout: tuple[ReportSection, ...]

    @property
    def schema(self) -> str:
        return f"sew.{self.command}/{self.version}"
