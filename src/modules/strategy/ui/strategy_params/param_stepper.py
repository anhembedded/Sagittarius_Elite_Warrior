"""The one thing `BotParamFieldWidget` needs from a screen's ViewModel.

@details The widget lets Up/Down and the mouse wheel step a numeric
parameter, and normalising that step (respecting the field's declared
`minval`/`maxval`/`step`) is Python-side work the widget deliberately does
not reimplement. Before `EPIC-022C` it took a whole `BackTestViewModel`
for that single call, which is what kept a general form widget welded to
one screen.

`architecture-rule.md` requires explicit contracts rather than implicit
duck-typing, so this is a `Protocol` and not "any object with the right
method": `BackTestViewModel` and `TradingViewModel` both satisfy it
structurally, and a third screen adding its own is told by the type
checker exactly what it owes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ParamStepper(Protocol):
    """@brief Normalises one keyboard/wheel step of a numeric parameter."""

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """@param direction `+1` for up/scroll-up, `-1` for down.
        @returns The new value as text, clamped to whatever the field's
        schema declared. Returns `raw_value` unchanged when the field is
        not numeric or not in the current schema.
        """
        ...
