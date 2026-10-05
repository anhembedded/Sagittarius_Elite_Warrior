"""The Data mode's commands (`EPIC-033D`): scan, sync, delete, export,
import, optimize and purge.

Each is one `QAction` in the Data menu, scoped to the mode; the three a user
runs most (scan, sync, sync all gaps) are also on its toolbar. They act on
the symbol, timeframe and range the mode's rail shows, so only Export and
Import, which ask for a file, end with "…". The two that delete ask first,
naming what is lost (`ui-presentation-rule.md` §10); that replaces the
screen's own confirmation overlays.

Qt-free, because `MarketDataModule.contribute()` imports it on a headless
run (`test_module_contribution_laziness.py`); the presenter's side is
`data_command_binding.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandConfirmation,
    CommandContribution,
)

DATA_MENU = ("&Data",)
_CONTRIBUTOR = "market_data"
_PREFIX = "market_data.data"

SCAN_STATUS = f"{_PREFIX}.scan_status"
SCAN_ALL = f"{_PREFIX}.scan_all"
SYNC_TIMEFRAME = f"{_PREFIX}.sync_timeframe"
SYNC_ALL_GAPS = f"{_PREFIX}.sync_all_gaps"
DELETE_SELECTED = f"{_PREFIX}.delete_selected"
EXPORT = f"{_PREFIX}.export"
IMPORT = f"{_PREFIX}.import"
OPTIMIZE = f"{_PREFIX}.optimize"
PURGE_ALL = f"{_PREFIX}.purge_all"


def data_commands(route: str) -> tuple[CommandContribution, ...]:
    """The commands of the Data mode at `route`, in menu order."""

    def command(
        command_id: str,
        text: str,
        *,
        on_toolbar: bool = False,
        shortcut: str | None = None,
        needs_input: bool = False,
        confirm: CommandConfirmation | None = None,
    ) -> CommandContribution:
        return CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=command_id,
            text=text,
            menu_path=DATA_MENU,
            mode=route,
            on_toolbar=on_toolbar,
            shortcut=shortcut,
            needs_input=needs_input,
            confirm=confirm,
        )

    return (
        command(SCAN_STATUS, "Scan &status", on_toolbar=True),
        command(SCAN_ALL, "Scan &all shards"),
        command(SYNC_TIMEFRAME, "S&ync timeframe", on_toolbar=True, shortcut="Ctrl+L"),
        command(SYNC_ALL_GAPS, "Sync all &gaps", on_toolbar=True),
        command(EXPORT, "&Export data…", needs_input=True),
        command(IMPORT, "&Import data…", needs_input=True),
        command(OPTIMIZE, "&Optimize database"),
        command(
            DELETE_SELECTED,
            "&Delete selected data",
            confirm=CommandConfirmation(
                title="Delete Data",
                consequence=(
                    "Every candle stored for the selected symbol and timeframe "
                    "is deleted. This cannot be undone."
                ),
                accept_text="Delete",
            ),
        ),
        command(
            PURGE_ALL,
            "&Purge all data",
            confirm=CommandConfirmation(
                title="Purge All Data",
                consequence=(
                    "Every stored candle of every symbol is deleted, with the "
                    "database files. This cannot be undone."
                ),
                accept_text="Purge",
            ),
        ),
    )
