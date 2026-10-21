"""`EPIC-043E` (B6) — a command on a mode's toolbar shows an icon beside its text.

The window sets `ToolButtonTextBesideIcon` on those toolbars (`BOT-164`), so a
command that names no icon is the one bare word in a row of pictured ones. A
checkable choice (a venue, a market) is exempt: its checked state is its signal.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets.asset_validator_extension import (
    REQUIRED_UI_ICONS,
)

_ICONS = Path(__file__).resolve().parents[4] / "src/support/ui_kit/assets/icons"
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
def test_every_toolbar_icon_is_a_file_the_boot_check_requires(mode: str) -> None:
    """The loader draws a blank icon for a missing file, so the test reads the file and the
    boot list instead."""
    for command in _toolbar_actions(mode):
        assert command.icon is not None
        assert (_ICONS / f"{command.icon}.svg").is_file(), command.command_id
        assert command.icon in REQUIRED_UI_ICONS, command.command_id


def test_stop_is_not_drawn_as_a_square() -> None:
    """A greyed outline square reads as a check box (`BOT-164`); Stop is mostly greyed."""
    stops = [
        c
        for mode in _MODES
        for c in _toolbar_actions(mode)
        if c.command_id.rsplit(".", 1)[-1] == "stop"
    ]
    assert stops
    assert {c.icon for c in stops} == {"octagon"}
