"""`ITradingSession`'s owner-budget promises, held by the fake and by the
real service over its real handlers (`EPIC-029` ADR D6).

@details The real service runs behind a dispatcher that routes each command
to the handler production binds for it, over a real `TradingSessionState`,
so "refused while trading is off" is the handler's own answer, not the
service's.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    OwnerInventoryDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget import (
    RegisterOwnerBudgetCommand,
    RegisterOwnerBudgetCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.trading_session_service import (
    TradingSessionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
    EarlierRunsRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    EMPTY_INVENTORY,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_trading_session import (
    OwnerBudgetContract,
    contract_registration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_owner_inventory_checkpoints import (
    FakeOwnerInventoryCheckpoints,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_SPOT = TradingVenue.SPOT_TESTNET


class _RoutingDispatcher(ICommandDispatcher):
    """Hands each command to the handler production binds for its type."""

    def __init__(self, handlers: dict[type, object]) -> None:
        self._handlers = handlers

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self._handlers[handler_class].execute(input_dto)  # type: ignore[attr-defined]


def _real_service(state: TradingSessionState) -> TradingSessionService:
    scopes = single_venue_scopes(venue_context(_SPOT), state)
    dispatcher = _RoutingDispatcher(
        {
            RegisterOwnerBudgetCommand: RegisterOwnerBudgetCommandHandler(
                scopes,
                OwnerInventoryDeriver(FakeOwnerInventoryCheckpoints()),
                DEFAULT_OWNER_BUDGET_CAPS,
            ),
        }
    )
    return TradingSessionService(dispatcher, state, _SPOT)


class TestTheFake(OwnerBudgetContract):
    @pytest.fixture
    def impl(self) -> FakeTradingSession:
        return FakeTradingSession()


class TestTheRealService(OwnerBudgetContract):
    @pytest.fixture
    def impl(self) -> TradingSessionService:
        return _real_service(TradingSessionState())


class TestTheFakesOwnBookkeeping:
    def test_a_registered_budget_is_kept_until_cleared(self) -> None:
        fake = FakeTradingSession()
        fake.set_enabled(enabled=True)

        assert fake.register_owner_budget(contract_registration()).inventory == (
            EMPTY_INVENTORY
        )
        assert set(fake.budgets) == {"bot-1"}

        fake.clear_owner_budget("bot-1")
        assert fake.budgets == {}

    def test_an_answer_taken_from_the_venue_is_asked_at_each_registration(
        self,
    ) -> None:
        """`BUG-194` — the inventory is the venue's record as it is at that
        registration, so the answer is asked every time, not kept."""
        fake = FakeTradingSession()
        fake.set_enabled(enabled=True)
        held = [Decimal(0)]
        fake.register_owner_budget_answers_from(
            lambda: OwnerBudgetRegistrationResult(
                None, OwnerInventory(held[0], Decimal(0))
            )
        )

        first = fake.register_owner_budget(contract_registration())
        held[0] = Decimal("0.5")
        second = fake.register_owner_budget(contract_registration())

        assert (first.inventory, second.inventory) == (
            OwnerInventory(Decimal(0), Decimal(0)),
            OwnerInventory(Decimal("0.5"), Decimal(0)),
        )

    def test_a_refusal_it_is_told_to_answer_registers_nothing(self) -> None:
        fake = FakeTradingSession()
        fake.set_enabled(enabled=True)
        fake.register_owner_budget_answers(
            OwnerBudgetRegistrationResult(
                OwnerBudgetRefusal.ABOVE_GLOBAL_CAP, exceeded_cap="max_open_orders"
            )
        )

        result = fake.register_owner_budget(contract_registration())

        assert (result.refusal, result.exceeded_cap) == (
            OwnerBudgetRefusal.ABOVE_GLOBAL_CAP,
            "max_open_orders",
        )
        assert fake.budgets == {}

    def test_an_emergency_stop_clears_every_budget(self) -> None:
        fake = FakeTradingSession()
        fake.set_enabled(enabled=True)
        fake.register_owner_budget(contract_registration("bot-1"))
        fake.register_owner_budget(contract_registration("bot-2"))

        fake.emergency_stop()

        assert fake.budgets == {}


def test_the_real_service_clears_a_budget_without_dispatching() -> None:
    """A dict removal with nothing to reconcile, as the lease is."""
    state = TradingSessionState()
    dispatcher = Mock(spec=ICommandDispatcher)
    service = TradingSessionService(dispatcher, state, _SPOT)

    service.clear_owner_budget("bot-1")

    dispatcher.dispatch.assert_not_called()


def test_the_fake_answers_what_earlier_runs_left_as_told_and_remembers_the_request() -> (
    None
):
    """`BUG-196` — the fake's helper is exercised here, beside the contract."""
    session = FakeTradingSession()
    request = EarlierRunsRequest(
        "a3f9c1", "BTCUSDT", "BTC", datetime(2026, 10, 1, tzinfo=UTC), datetime.now(UTC)
    )
    assert session.earlier_runs_inventory(request).quantity == 0

    session.earlier_runs_answers(EarlierRunsInventory(Decimal("0.5"), Decimal(10)))

    assert session.earlier_runs_inventory(request).quantity == Decimal("0.5")
    assert session.earlier_runs_requests == [request, request]
