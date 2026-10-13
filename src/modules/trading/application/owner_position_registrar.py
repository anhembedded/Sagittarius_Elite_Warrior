"""`EPIC-039D` — registering a Futures owner's budget: derive its position,
refuse a position that is not its own, install its book.

@details The Futures branch of `RegisterOwnerBudgetCommandHandler`, which
chooses between this and the Spot derivation once, by the venue's market: the
books themselves hold no venue test. In the order of the reads:

1. the history (`OwnerPositionDeriver`) and the owner's resting orders;
2. `positionRisk` for the symbol. If the owner's tagged fills add up to flat
   and the exchange holds a position beyond one step, that position is not the
   bot's: the registration is refused as `FOREIGN_POSITION`, recorded and never
   traded (Spot's "earlier runs", `BUG-196`);
3. the book is installed, and `positionRisk` is read once more and compared
   with it. A difference is returned in the result and published as an event,
   never silently overwritten: the exchange wins, and says so.

Every later `ACCOUNT_UPDATE` repeats step 3 (`position_state_reconciler`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerEventBuffer,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    InventoryBeyondLookbackError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_book import (
    OwnerPositionBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_deriver import (
    OwnerPositionDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_resting_orders import (
    resting_notional,
    resting_orders,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistration,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    ForeignPosition,
    PositionDivergence,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)

logger = logging.getLogger("App.Trading.OwnerPosition")


class OwnerPositionRegistrar:
    """Registers a Futures owner's budget over the venue's evidence."""

    def __init__(self, deriver: OwnerPositionDeriver) -> None:
        self._deriver = deriver

    def derive_and_install(
        self,
        registration: OwnerBudgetRegistration,
        scope: VenueTradingScope,
        epoch: int,
        held: OwnerEventBuffer,
    ) -> OwnerBudgetRegistrationResult:
        """@brief The registration's answer: the derived position when it was
        installed, a refusal otherwise."""
        scope.ports.history_reader.discard_remembered(registration.symbol)
        try:
            derivation = self._deriver.derive(
                registration, scope.ports.history_reader, datetime.now(UTC)
            )
            resting = resting_orders(registration, scope)
            exchange = _exchange_quantity(registration, scope)
            step = _step_of(registration, scope)
        except InventoryBeyondLookbackError as exc:
            logger.warning("Owner budget for %s refused: %s", registration.tag, exc)
            return _refused(OwnerBudgetRefusal.INVENTORY_BEYOND_LOOKBACK)
        except (AccountHistoryUnavailableError, SymbolRulesUnavailableError) as exc:
            logger.warning("Owner budget for %s refused: %s", registration.tag, exc)
            return _refused(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)
        derived = derivation.position.quantity
        if abs(derived) <= step < abs(exchange):
            foreign = ForeignPosition(registration.symbol, exchange)
            logger.warning(
                "Owner budget for %s refused: %s [foreign-position]",
                registration.tag,
                foreign.describe(),
            )
            return OwnerBudgetRegistrationResult(
                OwnerBudgetRefusal.FOREIGN_POSITION, foreign_position=foreign
            )
        book = OwnerPositionBook(
            registration, derivation.position, step, derivation.counted
        )
        for order in resting:
            book.adopt_open(order, resting_notional(order))
        if not scope.session_state.install_owner_book(
            registration.tag,
            book,
            expected_switch_epoch=epoch,
            held=held,
            counted=derivation.counted,
        ):
            return _refused(OwnerBudgetRefusal.TRADING_SWITCH_OFF)
        divergence = _cross_check(registration, scope)
        logger.info(
            "Owner budget registered for %s (%s) on %s %s: position %s, %d open order(s).",
            registration.owner_id,
            registration.tag,
            scope.venue.value,
            registration.symbol,
            book.position.quantity,
            len(resting),
        )
        return OwnerBudgetRegistrationResult(
            None, position=book.position, divergence=divergence
        )


def _exchange_quantity(
    registration: OwnerBudgetRegistration, scope: VenueTradingScope
) -> Decimal:
    """The signed position `positionRisk` reports on the symbol; zero when flat.
    @throws AccountHistoryUnavailableError The venue did not answer."""
    client = scope.ports.client_factory.create(OrderSubmissionMode.VALIDATE_ONLY)
    try:
        positions = client.get_positions(registration.symbol)
    # Converted at the seam, as `resting_orders` does.
    except Exception as exc:
        raise AccountHistoryUnavailableError(f"positionRisk: {exc}") from exc
    return sum((position.position_amt for position in positions), Decimal(0))


def _step_of(
    registration: OwnerBudgetRegistration, scope: VenueTradingScope
) -> Decimal:
    """The symbol's quantity step: the tolerance of every position comparison.
    @throws SymbolRulesUnavailableError The venue does not list the symbol, or
    its catalog could not be fetched."""
    metadata = scope.ports.metadata_provider.get_or_fetch(registration.symbol)
    if metadata is None:
        raise SymbolRulesUnavailableError(registration.symbol)
    return metadata.step_size


def _cross_check(
    registration: OwnerBudgetRegistration, scope: VenueTradingScope
) -> PositionDivergence | None:
    """Compares the installed book with a fresh `positionRisk`. A read that
    fails leaves the next `ACCOUNT_UPDATE`'s check to do it, and says so."""
    try:
        exchange = _exchange_quantity(registration, scope)
    except AccountHistoryUnavailableError as exc:
        logger.warning(
            "Position cross-check for %s skipped at registration: %s",
            registration.tag,
            exc,
        )
        return None
    divergence = scope.session_state.owner_books.cross_check_owner(
        registration.tag, exchange
    )
    if divergence is not None:
        logger.warning(
            "Position %s for %s on %s: derived %s, exchange %s [position-divergence]",
            divergence.kind.value,
            registration.tag,
            registration.symbol,
            divergence.derived,
            divergence.exchange,
        )
    return divergence


def _refused(refusal: OwnerBudgetRefusal) -> OwnerBudgetRegistrationResult:
    return OwnerBudgetRegistrationResult(refusal)
