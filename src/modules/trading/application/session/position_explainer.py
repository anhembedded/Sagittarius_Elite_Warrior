"""`BUG-250` — which positions of the account a closed order session may open over.

@details A closed session refuses every position it finds: this app never adopts or closes a
position it did not open (`SessionReadiness`). A host stop that leaves a Futures bot under its
protective stop (`EPIC-038M`, O12) leaves the bot's own position on the account, and the bot's
Resume (decision O2) is the one way back, so the refusal contradicted the policy that left it.

A position is **explained**, and so excused, only by the exchange's own evidence: the position of
each claim on its symbol is derived from the venue's history of the claim's tagged orders since its
run started (`OwnerPositionDeriver`, the derivation a budget registration uses, which also counts
fills that landed while the host was down), and the account's quantity must **equal** it. Both are exact
decimals, so there is no tolerance to absorb: one step of slack would admit a stray minimum-size
order beside a bot with no fills (decided in the review of the fix). The claim carries no figure
(`OwnerPositionClaim`): a bot's file never says how much it holds, it names whose tagged orders
count and from when. Everything else is named with its figures:

  · a position when no claim was offered at all (a Start, an arm, a manual order): said so, because
    the bot that owns it may be waiting, and "no bot claims it" would be false;
  · a symbol no claim names (a stray, or a position opened by hand);
  · a claimed symbol whose tagged history explains another quantity, more or less;
  · a claimed symbol whose history could not be read, or reaches back further than the venue
    keeps it: a position nobody can verify is not excused.

Reads nothing when the account holds no position, as on Spot, and with no claims every position is
named, so a Start, an arm and a manual order refuse as they did.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    InventoryBeyondLookbackError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_deriver import (
    OwnerPositionDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.unexplained_position import (
    PositionUnexplainedWhy,
    UnexplainedPosition,
)

logger = logging.getLogger("App.TradingSession")


class PositionExplainer:
    """Names the positions of an account that no claim's history explains."""

    def __init__(self, deriver: OwnerPositionDeriver) -> None:
        self._deriver = deriver

    def unexplained(
        self,
        scope: VenueTradingScope,
        positions: tuple[LivePosition, ...],
        claims: tuple[OwnerPositionClaim, ...],
    ) -> tuple[UnexplainedPosition, ...]:
        """@brief The positions of `positions` the claims do not explain, in the account's order;
        empty when every one is explained. Network reads when a claim names a held symbol: call
        it from a worker thread."""
        held = _held_by_symbol(positions)
        return tuple(
            judged
            for symbol, exchange in held.items()
            if (judged := self._judge(scope, symbol, exchange, claims)) is not None
        )

    def _judge(
        self,
        scope: VenueTradingScope,
        symbol: str,
        exchange: Decimal,
        claims: tuple[OwnerPositionClaim, ...],
    ) -> UnexplainedPosition | None:
        if not claims:
            return UnexplainedPosition(
                symbol, exchange, PositionUnexplainedWhy.NO_CLAIM_OFFERED
            )
        named = tuple(claim for claim in claims if claim.symbol == symbol)
        if not named:
            return UnexplainedPosition(
                symbol, exchange, PositionUnexplainedWhy.NO_CLAIM
            )
        try:
            derived = self._derived(scope, named)
        except (InventoryBeyondLookbackError, AccountHistoryUnavailableError) as error:
            logger.info(
                "Position on %s not excused: its history could not be verified (%s) "
                "[position-claim]",
                symbol,
                error,
            )
            return UnexplainedPosition(
                symbol, exchange, PositionUnexplainedWhy.HISTORY_UNVERIFIABLE
            )
        if exchange != derived:
            logger.info(
                "Position on %s not excused: the exchange holds %s, the claiming runs' "
                "tagged orders account for %s [position-claim]",
                symbol,
                exchange,
                derived,
            )
            return UnexplainedPosition(
                symbol, exchange, PositionUnexplainedWhy.DIFFERS_FROM_HISTORY, derived
            )
        logger.info(
            "Position on %s excused: %s on the exchange, %s from the tagged orders of %s "
            "[position-claim]",
            symbol,
            exchange,
            derived,
            ", ".join(claim.owner_id for claim in named),
        )
        return None

    def _derived(
        self, scope: VenueTradingScope, claims: tuple[OwnerPositionClaim, ...]
    ) -> Decimal:
        total = Decimal(0)
        for claim in claims:
            # A read from the venue, never a remembered one: the evidence is what decides.
            scope.ports.history_reader.discard_remembered(claim.symbol)
            derivation = self._deriver.derive(
                claim, scope.ports.history_reader, datetime.now(UTC)
            )
            total += derivation.position.quantity
        return total


def _held_by_symbol(positions: tuple[LivePosition, ...]) -> dict[str, Decimal]:
    """One-way mode: a symbol's positions add up to the one it holds."""
    held: dict[str, Decimal] = {}
    for position in positions:
        held[position.symbol] = (
            held.get(position.symbol, Decimal(0)) + position.position_amt
        )
    return held
