"""`EPIC-028K` — what a strategy card is bound to.

@details The Dev Board and both desks host the same card. Each builds one of
these from its own view model (`dev_board_card_binding`, `DeskView.attach`),
so the card names no screen's view model. A frozen value rather than a
`Protocol` over the hosts: the hosts expose these as Qt `@Property`s, which
`mypy` reads as the descriptor and not as the value it holds, so no host
could be checked against a structural contract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import SignalInstance
from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_card_view_model import (
    StrategyCardViewModel,
)


@dataclass(frozen=True)
class StrategyCardBinding:
    """The card's own state, whether trading is on, and when that changes."""

    strategy: StrategyCardViewModel
    #: The card locks while trading is on (`EPIC-023D`).
    is_trading_enabled: Callable[[], bool]
    trading_state_changed: SignalInstance
