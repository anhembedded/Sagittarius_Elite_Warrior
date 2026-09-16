"""`EPIC-022C` — the strategy-parameter form, shared by every screen that
configures a strategy.

@details These two modules were written for the Backtest screen and lived
inside `screens/backtest/`, but neither knows anything about Backtest:
`bot_params_form` reads `BaseStrategy.inputs` and returns plain schema/row
dicts, and `param_field` renders one of those rows. When the Trading
screen needed the same "Thông số Chiến lược" form, the choice was between
a cross-screen import — the dependency direction `EPIC-021L` had just
finished removing (`BUG-082`) — and moving them somewhere both screens may
legitimately depend on. This package is that somewhere.
"""

from .bot_params_form import (
    build_bot_params_rows,
    build_bot_params_schema,
    parse_bot_params,
    step_numeric_param_value,
)
from .param_field import BotParamFieldWidget
from .strategy_params_dialog import StrategyParamsDialog

__all__ = [
    "BotParamFieldWidget",
    "StrategyParamsDialog",
    "build_bot_params_rows",
    "build_bot_params_schema",
    "parse_bot_params",
    "step_numeric_param_value",
]
