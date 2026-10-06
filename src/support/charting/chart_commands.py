"""A chart's toolbar actions as menu commands (`BOT-156`).

`ChartToolbar` (in every `ChartCard`) holds the chart's navigation: the
pinned timeframes, More timeframes…, the zoom actions and Go live. A
toolbar's buttons take no keyboard focus, so a mode that shows a chart also
contributes these as commands in a menu (`ui-presentation-rule.md` §2, §6),
which `ChartCommandMirror` keeps in step with the chart in front.

The pinned timeframes are a person's favourites, changing per symbol; they
are not commands of their own. Each is a shortcut into the choice More
timeframes… offers, and says so (`MENU_EQUIVALENT`), so the menu holds that
command, from which every timeframe is reachable by keyboard.

Qt-free, because a module's `contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`).

The access keys avoid the letters of the Backtest mode's View → Chart items
(c, e, s, i, v, b), which share its submenu. The commands are one menu group,
the chart's navigation (`NAVIGATION_GROUP`, `BOT-157`), so a separator
divides them from a mode's own chart commands in the same menu.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

#: The dynamic property a toolbar action carries when its command is in a
#: menu under another name: the text of that menu command.
MENU_EQUIVALENT = "menuEquivalent"

#: The menu group of the chart's navigation commands (`BOT-157`).
NAVIGATION_GROUP = "chart.navigation"

MORE_TIMEFRAMES = "more_timeframes"
ZOOM_IN = "zoom_in"
ZOOM_OUT = "zoom_out"
ZOOM_IN_VERTICALLY = "zoom_in_vertically"
ZOOM_OUT_VERTICALLY = "zoom_out_vertically"
BOX_ZOOM = "box_zoom"
RESET_ZOOM = "reset_zoom"
GO_LIVE = "go_live"

#: Key -> menu text, in menu order. The texts read as the toolbar's do.
_TEXTS: tuple[tuple[str, str], ...] = (
    (MORE_TIMEFRAMES, "&More timeframes…"),
    (ZOOM_IN, "Zoom i&n"),
    (ZOOM_OUT, "Zoom &out"),
    (ZOOM_IN_VERTICALLY, "Zoom in ver&tically"),
    (ZOOM_OUT_VERTICALLY, "Zoom out verticall&y"),
    (BOX_ZOOM, "Box &zoom"),
    (RESET_ZOOM, "&Reset zoom"),
    (GO_LIVE, "&Go live"),
)
#: The keys whose command keeps a checked state (a one-shot tool).
CHECKABLE = frozenset({BOX_ZOOM})
#: The platform's own zoom keys (`QKeySequence.StandardKey`; Ctrl++ and
#: Ctrl+- on Windows), which a standard command takes
#: (`ui-presentation-rule.md` §11). Only the mode in front holds its
#: commands' shortcuts, so Market and Backtest never claim them together.
_STANDARD_KEYS = {ZOOM_IN: "ZoomIn", ZOOM_OUT: "ZoomOut"}


def chart_command_id(prefix: str, key: str) -> str:
    return f"{prefix}.chart.{key}"


def chart_commands(
    contributor_id: str, prefix: str, route: str, menu_path: tuple[str, ...]
) -> tuple[CommandContribution, ...]:
    """The chart's commands for the mode at `route`, in `menu_path`."""
    return tuple(
        CommandContribution(
            contributor_id=contributor_id,
            command_id=chart_command_id(prefix, key),
            text=text,
            menu_path=menu_path,
            mode=route,
            checkable=key in CHECKABLE,
            needs_input=key == MORE_TIMEFRAMES,
            standard_shortcut=_STANDARD_KEYS.get(key),
            group=NAVIGATION_GROUP,
        )
        for key, text in _TEXTS
    )


def chart_command_keys() -> tuple[str, ...]:
    return tuple(key for key, _text in _TEXTS)
