"""`EPIC-029` ADR D6 — registering an owner budget.

@details The order of the checks is the order of their cost: the refusals
that need no network first (the venue, the switch, the symbol, the global
caps, the tag), then the two reads of exchange evidence, the history (the
inventory) and the open orders (what the owner already has resting, after a
restart or during a reconciliation). The switch epoch is read before those
reads and checked when the book is installed, so a disable that lands
meanwhile wins and nothing is installed into the next session. The tag's
fills and ends are held from before the reads until the install, which
replays the ones the history did not count, so a fill landing between the
read and the install is counted once (`OwnerBooks`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_book import (
    OwnerBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerEventBuffer,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    InventoryBeyondLookbackError,
    OwnerInventoryDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_registrar import (
    OwnerPositionRegistrar,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_resting_orders import (
    resting_notional,
    resting_orders,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget.command import (
    RegisterOwnerBudgetCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistration,
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.CommandHandler")

#: `(market, budget declares no Futures limits)` pairs a registration may be
#: made for: a Spot budget has none, a USDⓈ-M Futures budget has them.
_BUDGET_FITS_VENUE = frozenset(
    {(MarketType.SPOT, True), (MarketType.FUTURES_USD_M, False)}
)


class RegisterOwnerBudgetCommandHandler(
    ICommandHandler[RegisterOwnerBudgetCommand, OwnerBudgetRegistrationResult]
):
    """Derives the owner's inventory and open orders from the venue, then
    installs its book for this session."""

    def __init__(
        self,
        scopes: VenueTradingScopes,
        deriver: OwnerInventoryDeriver,
        positions: OwnerPositionRegistrar,
        caps: OwnerBudgetCaps,
    ) -> None:
        self._scopes = scopes
        self._deriver = deriver
        self._positions = positions
        self._caps = caps

    def execute(
        self, command: RegisterOwnerBudgetCommand
    ) -> OwnerBudgetRegistrationResult:
        registration = command.registration
        market = command.venue.market_type
        if (market, registration.budget.futures is None) not in _BUDGET_FITS_VENUE:
            return _refused(OwnerBudgetRefusal.BUDGET_NOT_FOR_VENUE)
        scope = self._scopes.get(command.venue)
        refusal = self._cheap_refusal(registration, scope)
        if refusal is not None:
            return refusal
        epoch = scope.session_state.switch_epoch
        books = scope.session_state.owner_books
        held = books.open_buffer(registration.tag, registration.symbol)
        try:
            if market is MarketType.FUTURES_USD_M:
                return self._positions.derive_and_install(
                    registration, scope, epoch, held
                )
            return self._derive_and_install(registration, command, scope, epoch, held)
        finally:
            books.close_buffer(held)

    def _derive_and_install(
        self,
        registration: OwnerBudgetRegistration,
        command: RegisterOwnerBudgetCommand,
        scope: VenueTradingScope,
        epoch: int,
        held: OwnerEventBuffer,
    ) -> OwnerBudgetRegistrationResult:
        # A registration derives from exchange evidence (ADR D6), and the
        # evidence must be the exchange as it is now: the history reader's
        # memory of the last few seconds would replace a live owner book with
        # one that missed their fills (`EPIC-035B`).
        scope.ports.history_reader.discard_remembered(registration.symbol)
        try:
            derivation = self._deriver.derive(
                registration, scope.ports.history_reader, datetime.now(UTC)
            )
            resting = resting_orders(registration, scope)
        except InventoryBeyondLookbackError as exc:
            logger.warning("Owner budget for %s refused: %s", registration.tag, exc)
            return _refused(OwnerBudgetRefusal.INVENTORY_BEYOND_LOOKBACK)
        except AccountHistoryUnavailableError as exc:
            logger.warning("Owner budget for %s refused: %s", registration.tag, exc)
            return _refused(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)
        book = OwnerBook(registration, derivation.inventory, derivation.counted)
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
        inventory = book.inventory
        logger.info(
            "Owner budget registered for %s (%s) on %s %s: %s held, %d open order(s).",
            registration.owner_id,
            registration.tag,
            command.venue.value,
            registration.symbol,
            inventory.quantity,
            len(resting),
        )
        return OwnerBudgetRegistrationResult(None, inventory)

    def _cheap_refusal(
        self, registration: OwnerBudgetRegistration, scope: VenueTradingScope
    ) -> OwnerBudgetRegistrationResult | None:
        if not scope.session_state.enabled:
            return _refused(OwnerBudgetRefusal.TRADING_SWITCH_OFF)
        if not registration.is_quoted_in_budget_asset:
            return _refused(OwnerBudgetRefusal.SYMBOL_NOT_SUPPORTED)
        cap = self._caps.exceeded_by(registration.budget)
        if cap is not None:
            return OwnerBudgetRegistrationResult(
                OwnerBudgetRefusal.ABOVE_GLOBAL_CAP, exceeded_cap=cap
            )
        holder = scope.session_state.owner_books.holder_of(registration.tag)
        if holder is not None and holder != registration.owner_id:
            return _refused(OwnerBudgetRefusal.TAG_HELD_BY_ANOTHER_OWNER)
        return None


def _refused(refusal: OwnerBudgetRefusal) -> OwnerBudgetRegistrationResult:
    return OwnerBudgetRegistrationResult(refusal)
