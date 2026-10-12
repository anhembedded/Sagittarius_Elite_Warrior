"""Print a command's `Report` in the format the operator asked for (`EPIC-038C`).

A module's command handler cannot import the CLI host (a module reads another
package only through its `contracts/`, `architecture-rule.md` §3), so it asks
this port, which the shell binds to `emit_report` over the registered renderers.
The port is the narrow role a report command needs (Interface Segregation): it
cannot register a format, only use the one the arguments name.

@par Extension cases
  · a new output format - a renderer registered in `IReportFormats`; this port
    and the commands that call it do not change.
"""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report


class IReportPrinter(ABC):
    @abstractmethod
    def print_report(
        self, report: Report, args: argparse.Namespace
    ) -> CliOutcome | None:
        """Print `report` to standard output.

        Returns a usage outcome, and prints nothing, when the arguments name a
        format that does not exist or contradict each other; `None` otherwise.
        The command keeps the exit code its own findings deserve.
        """
