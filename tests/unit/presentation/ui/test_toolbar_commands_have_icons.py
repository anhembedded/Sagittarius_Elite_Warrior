"""`EPIC-043E` (B6) — a command on a mode's toolbar shows an icon beside its text.

The window sets `ToolButtonTextBesideIcon` on those toolbars (`BOT-164`), so a
command that names no icon is the one bare word in a row of pictured ones. A
checkable choice (a venue, a market) is exempt: its checked state is its signal.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_commands import (
    backtest_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_commands import (
    data_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    trade_commands,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets.icon_loader import (
    get_icon_loader,
)

_MODES: dict[str, Callable[[], tuple[CommandContribution, ...]]] = {
    "backtest": lambda: backtest_commands("backtest"),
    "bots": lambda: bots_commands("bots"),
    "data": lambda: data_commands("data"),
    "market": lambda: market_commands("market"),
    "trade": lambda: trade_commands("trade", [TradingVenue.FUTURES_TESTNET]),
}


def _toolbar_actions(mode: str) -> list[CommandContribution]:
    return [c for c in _MODES[mode]() if c.on_toolbar and not c.checkable]


@pytest.mark.parametrize("mode", sorted(_MODES))
def test_every_toolbar_command_names_an_icon(mode: str) -> None:
    bare = [c.command_id for c in _toolbar_actions(mode) if c.icon is None]
    assert bare == []


@pytest.mark.parametrize("mode", sorted(_MODES))
def test_every_toolbar_icon_is_a_file_that_loads(qapp: object, mode: str) -> None:
    for command in _toolbar_actions(mode):
        assert command.icon is not None
        icon = get_icon_loader().get_icon(command.icon, "#000000", 24)
        assert not icon.isNull(), command.command_id
