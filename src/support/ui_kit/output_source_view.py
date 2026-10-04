"""A view that offers its log to the Output pane (`EPIC-033F`).

Satisfies `IOutputSource` once: a view sets `_output` to its channel when its
view model, which owns the lines, is bound. A view whose presenter binds none
(a desk whose venue is disabled in this run) offers no channel.
"""

from __future__ import annotations

from sagittarius_engine.extensions.pyside_mvc import BaseView
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import (
    OutputChannel,
)


class OutputSourceView(BaseView):
    """A `BaseView` whose log is one channel of the Output pane."""

    _output: OutputChannel | None = None

    def output_channel(self) -> OutputChannel | None:
        return self._output
