"""`EPIC-034G` — the chart's live stream as a menu command, as data.

The menu bar is the complete catalogue of commands (`ui-presentation-rule.md`
§6), so the chip's Go live / Cancel / Stop live / Retry has one entry in the
menu of every mode that shows a live chart: a checkable **Live stream**,
checked while the chart connects or is live. Checking it asks for what the
chart's state offers (Go live, or Retry from Error); unchecking it, Cancel or
Stop live. A command whose text follows its state is the extension
`command_contribution.py` lists; a checkable command needs none, and the
chip beside the chart still says each state in words.

Qt-free, like `chart_commands.py`: a module's `contribute()` imports it
without pulling Qt in (`test_module_contribution_laziness.py`). The mirror
that drives the chart's action is `live_stream_mirror.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    chart_command_id,
)

LIVE_STREAM = "live_stream"

#: The group the entry sits in, apart from the chart's navigation.
LIVE_STREAM_GROUP = "chart.live_stream"


def live_stream_command(
    contributor_id: str,
    prefix: str,
    route: str,
    menu_path: tuple[str, ...],
    text: str = "&Live stream",
) -> CommandContribution:
    """The mode's Live stream entry in `menu_path`. `text` carries the
    access key, which must be free in that menu."""
    return CommandContribution(
        contributor_id=contributor_id,
        command_id=chart_command_id(prefix, LIVE_STREAM),
        text=text,
        menu_path=menu_path,
        mode=route,
        checkable=True,
        group=LIVE_STREAM_GROUP,
    )
