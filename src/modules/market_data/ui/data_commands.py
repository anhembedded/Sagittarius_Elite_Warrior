"""The Data mode's commands (`EPIC-033D`, laid out by `EPIC-033J`).

Each is one `QAction` in the Data menu, scoped to the mode, in HLD §11.2.3's
order where the table lists it (Sync history… Ctrl+L, Check gaps, Repair
gap, Delete data) and then the interim ones it names (scans, Sync all gaps,
Export, Import, Optimize, Purge), with Inspect candles and Stop added by the
mode. The frequent ones are also on its toolbar.

- **What they act on.** The shard selected in the coverage table: Check
  gaps, Inspect candles, Delete data and Export; Sync history… opens on it.
  Repair gap acts on the gap selected in the Gaps panel, Repair all gaps on
  every gap it lists. Each is disabled while what it needs is not there, and
  every one but Stop while a task runs.
- **"…"** ends the commands that ask before acting (Sync history…, Export
  data…, Import data…). The two that delete ask first, naming what is lost
  (`ui-presentation-rule.md` §10), and take no "…". Delete data asks with
  the table's question, which names the shard; Purge all data with the
  Engine's confirmation.
- **Stop** stops the running task: an operation with side effects stops, it
  is not cancelled (§10).

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

SYNC_HISTORY = f"{_PREFIX}.sync_history"
CHECK_GAPS = f"{_PREFIX}.check_gaps"
REPAIR_GAP = f"{_PREFIX}.repair_gap"
REPAIR_ALL_GAPS = f"{_PREFIX}.repair_all_gaps"
INSPECT_CANDLES = f"{_PREFIX}.inspect_candles"
STOP = f"{_PREFIX}.stop"
SCAN_STATUS = f"{_PREFIX}.scan_status"
SCAN_ALL = f"{_PREFIX}.scan_all"
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
        command(
            SYNC_HISTORY,
            "&Sync history…",
            on_toolbar=True,
            shortcut="Ctrl+L",
            needs_input=True,
        ),
        command(CHECK_GAPS, "&Check gaps", on_toolbar=True),
        command(REPAIR_GAP, "&Repair gap", on_toolbar=True),
        command(REPAIR_ALL_GAPS, "Repair a&ll gaps"),
        command(INSPECT_CANDLES, "&Inspect candles"),
        command(STOP, "St&op", on_toolbar=True),
        command(SCAN_STATUS, "Scan s&tatus", on_toolbar=True),
        command(SCAN_ALL, "Scan &all shards"),
        command(SYNC_ALL_GAPS, "Sync all &gaps"),
        command(EXPORT, "&Export data…", needs_input=True),
        command(IMPORT, "I&mport data…", needs_input=True),
        command(OPTIMIZE, "Optimi&ze database"),
        # Delete data asks through the coverage table's own question, which
        # names the shard and its candle count; a declared confirmation is
        # fixed text and could only say "the selected symbol" (review of
        # PR #354).
        command(DELETE_SELECTED, "&Delete data"),
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
