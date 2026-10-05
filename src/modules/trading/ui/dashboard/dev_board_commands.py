"""The Dev Board's commands (`EPIC-033D`): Reload history, Enable live
trading, Emergency stop and New order.

Each is one `QAction` in the Trade menu and on the Dev Board's toolbar, scoped
to its mode. Enable live trading and Emergency stop reuse the desks' words,
because they drive the same session controls (`DeskSessionControls`);
Emergency stop asks first, Enable does not (`desk_commands.py` says why).
New order ends with "…": it opens the order dialog before anything is sent.

Qt-free, because `TradingModule.contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`); the presenter's side is
`dev_board_command_binding.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandConfirmation,
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_commands import (
    TRADE_MENU,
)

_CONTRIBUTOR = "trading"
_PREFIX = "trading.dev_board"

RELOAD_HISTORY = f"{_PREFIX}.reload_history"
ENABLE_TRADING = f"{_PREFIX}.enable_trading"
EMERGENCY_STOP = f"{_PREFIX}.emergency_stop"
NEW_ORDER = f"{_PREFIX}.new_order"


def dev_board_commands(route: str) -> tuple[CommandContribution, ...]:
    """The commands of the Dev Board at `route`."""
    return (
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=RELOAD_HISTORY,
            text="&Reload history",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=ENABLE_TRADING,
            text="&Enable live trading",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            checkable=True,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=EMERGENCY_STOP,
            text="Emergency &stop",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            shortcut="F8",
            confirm=CommandConfirmation(
                title="Emergency stop",
                consequence=(
                    "Live trading turns off, every open order is cancelled, and "
                    "what the session holds is closed at market."
                ),
                accept_text="Stop everything",
            ),
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=NEW_ORDER,
            text="&New order…",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            shortcut="F9",
            needs_input=True,
        ),
    )
