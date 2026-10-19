"""The registry of report renderers: lookup for a command, registration for the composition root.

`EPIC-038B`. One class implements the narrow lookup port (`IReportFormats`)
and adds `register`, the same two-roles-one-object split `CliRegistry` uses.
Registering a name twice is a programming error and raises, rather than
letting whichever registered last quietly win.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_report_formats import (
    IReportFormats,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_renderer import (
    IReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.json_report_renderer import (
    JsonReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)

TEXT_FORMAT = "text"
JSON_FORMAT = "json"


class ReportFormats(IReportFormats):
    def __init__(self) -> None:
        self._renderers: dict[str, IReportRenderer] = {}

    @classmethod
    def default(cls, text: IReportRenderer | None = None) -> ReportFormats:
        """The two formats every report command offers; `text` replaces the
        plain text renderer by one that wraps it (`BOT-195`)."""
        formats = cls()
        formats.register(TEXT_FORMAT, text or TextReportRenderer())
        formats.register(JSON_FORMAT, JsonReportRenderer())
        return formats

    def register(self, name: str, renderer: IReportRenderer) -> None:
        if not name or name != name.strip().lower() or " " in name:
            raise ValueError(f"a report format name is a lowercase word, not {name!r}")
        if name in self._renderers:
            raise ValueError(f"the report format {name!r} is already registered")
        self._renderers[name] = renderer

    def names(self) -> tuple[str, ...]:
        return tuple(self._renderers)

    def get(self, name: str) -> IReportRenderer | None:
        return self._renderers.get(name)
