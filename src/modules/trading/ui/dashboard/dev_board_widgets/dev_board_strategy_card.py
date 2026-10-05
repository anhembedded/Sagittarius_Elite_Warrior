"""The Dev Board's copy of the desks' strategy card (`EPIC-028K`); the card
moved to the desks in `EPIC-033P` and names no screen, so the Dev Board binds
it to its own view model here."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.strategy_card.strategy_card import (
    StrategyCard,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.strategy_card.strategy_card_binding import (
    StrategyCardBinding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_card_view_model import (
    StrategyCardViewModel,
)

from ..dashboard_view_model import DashboardQmlViewModel


def dev_board_strategy_card(
    view_model: DashboardQmlViewModel, market_type: MarketType | None
) -> StrategyCard:
    """The card, bound to the Dev Board's view model.

    @details `DashboardQmlViewModel.strategy` is a PySide6 `@Property`;
    `mypy` reads the descriptor itself (`Property`) rather than the
    `StrategyCardViewModel` it holds at runtime, the systemic false positive
    `pyproject.toml`'s `[tool.mypy]` exclude list documents for
    `presentation/` (a stub/plugin decision, not a per-line fix). Narrowed
    once here."""
    strategy: StrategyCardViewModel = view_model.strategy  # type: ignore[assignment]
    binding = StrategyCardBinding(
        strategy=strategy,
        is_trading_enabled=lambda: bool(view_model.enabled),
        trading_state_changed=view_model.tradingStateChanged,
    )
    return StrategyCard(binding, market_type=market_type)
