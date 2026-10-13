"""`EPIC-039H` — what a running position bot's risk watch reads from the exchange (`EPIC-039F`'s ports).

  · **`PositionRiskSnapshots`** (`IRiskSnapshotSource`): the signed position and the liquidation
    price `positionRisk` reports on the bot's symbol, with the mark price from `premiumIndex`
    (read for a flat symbol too). The liquidation price is the exchange's, never computed here.
  · **`PositionRechecks`** (`IPositionRecheck`): the second look before the bot halts on a
    divergence. It registers the budget again, which derives the position from the exchange's
    record of the bot's fills afresh and compares it with a fresh `positionRisk`; a registration
    that the exchange's position makes `FOREIGN_POSITION` (the bot's fills are flat and a position
    stands) is the same disagreement, said in the divergence's own terms.

A read that fails is a `RiskReadError`: it says nothing about the risk, and the watch keeps its
last reading, which ages into UNKNOWN.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
    refusal_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_reads import (
    IPositionRecheck,
    IRiskSnapshotSource,
    RiskReadError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import RiskSnapshot
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
    PositionDivergenceKind,
)


class PositionRiskSnapshots(IRiskSnapshotSource):
    def __init__(self, context: GridRunContext, ports: IVenueTradingPorts) -> None:
        self._context = context
        self._ports = ports

    def read(self) -> RiskSnapshot:
        definition = self._context.state.bot.definition
        symbol = definition.symbol
        venue = self._ports.get(definition.venue)
        try:
            positions = venue.account_snapshot.open_positions()
            mark = venue.order_entry_terms.mark_price_for(symbol)
        except Exception as exc:
            raise RiskReadError(f"{symbol}: {exc}") from exc
        if isinstance(mark, NotApplicable):
            raise RiskReadError(f"{symbol}: the venue reports no mark price")
        mine = tuple(p for p in positions if p.symbol == symbol)
        liquidation = next(
            (p.liquidation_price for p in mine if p.liquidation_price is not None), None
        )
        return RiskSnapshot(
            sum((p.position_amt for p in mine), Decimal(0)),
            mark.mark_price,
            liquidation,
            self._context.state.now(),
        )


class PositionRechecks(IPositionRecheck):
    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._housekeeping = GridHousekeeping(context)

    def recheck(self, divergence: PositionDivergence) -> PositionDivergence | None:
        try:
            registration = self._housekeeping.register()
        except Exception as exc:
            raise RiskReadError(f"the position was not re-derived: {exc}") from exc
        if registration.refusal is OwnerBudgetRefusal.FOREIGN_POSITION:
            foreign = registration.foreign_position
            if foreign is None:
                raise RiskReadError("a foreign position was refused and not described")
            return PositionDivergence(
                PositionDivergenceKind.POSITION_MISMATCH,
                divergence.owner_id,
                divergence.tag,
                divergence.symbol,
                Decimal(0),
                foreign.quantity,
            )
        if not registration.registered:
            raise RiskReadError(
                f"the position was not re-derived: {refusal_text(registration)}"
            )
        return registration.divergence
