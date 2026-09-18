"""`SignalGeneratedEvent` — relocated from `modules.strategy.contracts.events`
so publishing a signal never requires `trading` (or any other subscriber
outside `strategy`) to import `modules.strategy.contracts` for the event
type alone.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8. `strategy` already legally depends on `trading`
(`strategy.dependencies` names it), so `strategy`'s own publisher
(`strategy_engine.py`) importing this relocated type costs nothing; every
other subscriber (`backtesting`, whose `dependencies` already names both
`strategy` and `trading`) is unaffected the same way.

`Signal` itself stays put in `modules.strategy.contracts.signal` — it is
only ever a type-checking-time reference here (`from __future__ import
annotations` makes the annotation a lazy string, and
`imported_modules()`/the module-boundary and dependency-declaration guards
both skip `if TYPE_CHECKING:` bodies), so importing it under `TYPE_CHECKING`
costs zero runtime dependency and would otherwise reintroduce, in this one
relocated file, the exact `trading -> strategy` edge this whole step exists
to eliminate.

@par Not `frozen` — inherited from the original location, unchanged
See the original `modules/strategy/contracts/events/signal_generated_event.py`
history for why: `BaseEvent` (Shared Kernel) cannot be frozen, so a
dataclass inheriting it cannot be either. Treat as read-only by convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sagittarius_engine.domain.base_event import BaseEvent

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal


@dataclass
class SignalGeneratedEvent(BaseEvent):
    """@brief Domain event: a strategy produced one `Signal`."""

    signal: Signal
