"""`EPIC-039H` — what a position venue settles before its first order (DESIGN §9.1).

@details Two things the Spot start has no counterpart for, in this order and both before any
order is sent:

  1. **The venue's settings** (`IVenueSettingsGate.ensure`, `EPIC-039E`): the symbol's margin type
     and leverage are made to be the bot's, read back and compared. A change is signed account
     activity, so it needs the order session open — the start's preconditions opened it — and it
     is refused with an order or a position standing. A refusal names both values.
  2. **The plan's liquidation risk** (`IRiskGuard.judge_plan`, `EPIC-039F`): the ladder is judged
     against the symbol as it is now (its brackets read again, the mark price, the setting the gate
     just proved). A REFUSED verdict is the start's refusal, in the verdict's words; a WARNING is
     logged and the start goes on.

The daily ATR the stop-distance warning compares with is not read here (the executor has no
candles); that one WARNING is judged on the screen's plan, which has them.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_margin_mode import (
    GRID_MARGIN_MODE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.symbol_brackets import (
    SymbolBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_guard import IRiskGuard
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class FuturesStartChecks:
    """Settles the venue's settings and judges the plan's risk; answers why not, in words."""

    def __init__(
        self,
        context: GridRunContext,
        gate: IVenueSettingsGate,
        guard: IRiskGuard,
        reads: FuturesStartReads,
    ) -> None:
        self._context = context
        self._gate = gate
        self._guard = guard
        self._reads = reads

    def refusal(self, plan: GridPlan) -> str | None:
        """@return The sentence that refuses the start, or `None` when it may go on."""
        context = self._context
        definition = context.state.bot.definition
        ensured = self._gate.ensure(
            GateRequest(
                definition.venue,
                definition.symbol,
                context.params.leverage,
                GRID_MARGIN_MODE,
                bot_owner_id(context.state.bot_id),
            )
        )
        if not ensured.ensured:
            return f"the venue's settings could not be made the bot's: {ensured.detail}"
        inputs = self._reads.risk_inputs(plan)
        if isinstance(inputs, str):
            return inputs
        verdicts = self._guard.judge_plan(inputs)
        for verdict in verdicts:
            _log(context.state.bot_id, verdict)
        refused = [verdict.reason for verdict in verdicts if verdict.refuses]
        return "; ".join(refused) if refused else None


def _log(bot_id: str, verdict: Verdict) -> None:
    logger.info(
        "Bot %s: plan risk %s %s: %s [plan-risk]",
        bot_id,
        verdict.severity.value,
        verdict.code,
        verdict.reason,
    )


class FuturesStartReads:
    """The venue facts the plan-time guard is judged with, read at the start."""

    def __init__(
        self,
        context: GridRunContext,
        ports: IVenueTradingPorts,
        brackets: SymbolBrackets,
        thresholds: FuturesGridThresholds,
    ) -> None:
        self._context = context
        self._ports = ports
        self._brackets = brackets
        self._thresholds = thresholds

    def risk_inputs(self, plan: GridPlan) -> PlanRiskInputs | str:
        """The guard's inputs, or the sentence that says which fact could not be read."""
        definition = self._context.state.bot.definition
        terms = self._ports.get(definition.venue).order_entry_terms
        try:
            brackets = self._brackets.refresh(definition.venue, definition.symbol)
            setting = terms.futures_setting_for(definition.symbol)
            mark = terms.mark_price_for(definition.symbol)
        except Exception as exc:  # noqa: BLE001 - converted at the seam: a fact the guard needs that could not be read is a start refusal in words, never a raise and never a guess
            logger.warning(
                "Bot %s: the plan's risk could not be judged: %s [plan-risk]",
                self._context.state.bot_id,
                exc,
            )
            return f"the plan's liquidation risk could not be judged: {exc}"
        if isinstance(setting, NotApplicable) or isinstance(mark, NotApplicable):
            return (
                "the venue has no leverage settings or mark price to judge the plan by"
            )
        return PlanRiskInputs(
            self._context.params,
            plan,
            setting,
            brackets,
            mark.mark_price,
            self._thresholds,
        )
