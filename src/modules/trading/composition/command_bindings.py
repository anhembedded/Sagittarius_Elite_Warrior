"""trading's write side: the commands that change the live trading session,
place or cancel an order, or change a Futures symbol's leverage or margin
mode (`EPIC-028F`).

`EPIC-025E` PR 4.4f-4 — moved out of `binance_bot_module.py`, same shape
`backtesting/composition/command_bindings.py` (PR 4.4f-1) and `strategy/
composition/command_bindings.py` (PR 4.4f-2) already used.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage import (
    ChangeLeverageCommand,
    ChangeLeverageCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type import (
    ChangeMarginTypeCommand,
    ChangeMarginTypeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.submit_order import (
    SubmitOrderCommand,
    SubmitOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.disable_trading import (
    DisableTradingCommand,
    DisableTradingCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.enable_trading import (
    EnableTradingCommand,
    EnableTradingCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget import (
    RegisterOwnerBudgetCommand,
    RegisterOwnerBudgetCommandHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_commands(container: IContainer) -> None:
    """Route each trading command type to the handler that executes it."""
    container.bind(SubmitOrderCommand, SubmitOrderCommandHandler)
    container.bind(EnableTradingCommand, EnableTradingCommandHandler)
    container.bind(DisableTradingCommand, DisableTradingCommandHandler)
    container.bind(ExecuteOrderCommand, ExecuteOrderCommandHandler)
    container.bind(EmergencyStopCommand, EmergencyStopCommandHandler)
    container.bind(RegisterOwnerBudgetCommand, RegisterOwnerBudgetCommandHandler)
    container.bind(CancelOrderCommand, CancelOrderCommandHandler)
    container.bind(ChangeLeverageCommand, ChangeLeverageCommandHandler)
    container.bind(ChangeMarginTypeCommand, ChangeMarginTypeCommandHandler)
