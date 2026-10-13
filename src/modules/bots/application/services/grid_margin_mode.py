"""`EPIC-039` decision O5 — the margin mode a Grid bot asks of its venue: Isolated only.

@details One constant for the executor factory (the running bot's settings check) and the
start's own checks (the gate's `ensure`), so the two can never ask for different modes. A bot that
may ask for Cross reads it from its params instead, and this goes.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode

GRID_MARGIN_MODE = MarginMode.ISOLATED
