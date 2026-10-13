"""`EPIC-039E` — a running bot's question: does the venue still hold what I asked for?

@details A `SettingsCheck` is the settings gate's read-only `verify`, already bound to the
bot's request (`functools.partial(gate.verify, request)`), so the reconciler holds no venue,
symbol or leverage. Spot has nothing to hold: `no_settings_to_check` answers `ENSURED`.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    ENSURED,
    GateResult,
)

type SettingsCheck = Callable[[], GateResult]


def no_settings_to_check() -> GateResult:
    return ENSURED
