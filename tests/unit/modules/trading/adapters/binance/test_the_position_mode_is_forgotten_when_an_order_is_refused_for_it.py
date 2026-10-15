"""`BUG-216` - the minute a One-way position mode is trusted ends when the exchange says it is not One-way.

@details An order is sent as One-way (`positionSide=BOTH`). If the user switched the account to Hedge
mode on the exchange, the exchange refuses it by name, `-4061`, and the next connection check must
read the mode instead of trusting the kept answer for the rest of the minute. The memory is shared
by the venue's account reader and its trading clients; `VenueAssembly` is where that is wired, so
it is asserted on the assembly's own graph (`CS-002`).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.ordered_secret_stores import (
    OrderedSecretStores,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.position_mode_memory import (
    TTL_SECONDS,
    PositionModeMemory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    SharedVenueInputs,
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.test_futures_trading_client import (
    _client,
    _order,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 500.0

    def __call__(self) -> float:
        return self.now


def _refusal(code: int) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message, exc.status_code = code, f"error {code}", 400
    exc.response = Mock(text="", headers={})
    exc.request = None
    return exc


def test_the_memory_trusts_a_one_way_answer_for_a_minute_and_forgets_on_request() -> (
    None
):
    clock = _Clock()
    memory = PositionModeMemory(clock)
    assert not memory.one_way_is_current(), "nothing read yet"

    memory.remember_one_way()
    clock.now += TTL_SECONDS - 1
    assert memory.one_way_is_current()
    clock.now += 1
    assert not memory.one_way_is_current(), "a minute is the limit"

    memory.remember_one_way()
    memory.forget()
    assert not memory.one_way_is_current()


def test_an_order_refused_for_its_position_side_makes_the_next_check_read_the_mode() -> (
    None
):
    memory = PositionModeMemory(_Clock())
    memory.remember_one_way()
    raw = Mock()
    raw.futures_create_order.side_effect = _refusal(-4061)
    client = _client(raw, OrderSubmissionMode.LIVE)
    client._position_mode = memory

    with pytest.raises(OrderRejectedByExchangeError):
        client.place_order(_order())

    assert not memory.one_way_is_current()


def test_any_other_refusal_leaves_the_kept_answer_alone() -> None:
    memory = PositionModeMemory(_Clock())
    memory.remember_one_way()
    raw = Mock()
    raw.futures_create_order.side_effect = _refusal(-2010)
    client = _client(raw, OrderSubmissionMode.LIVE)
    client._position_mode = memory

    with pytest.raises(OrderRejectedByExchangeError):
        client.place_order(_order())

    assert memory.one_way_is_current()


def test_the_venue_assembly_gives_its_reader_and_its_clients_one_memory() -> None:
    shared = SharedVenueInputs(
        container=Mock(),
        secrets_file_path=str(Path("unused")),
        session_states=VenueSessionStates(),
        secret_store=OrderedSecretStores.single(InMemorySecretStore()),
        instance=InstanceAccess.unguarded(),
    )
    assembly = VenueAssembly(TradingVenue.FUTURES_TESTNET, shared)

    reader = assembly.account_reader
    client = assembly.client_factory.create(OrderSubmissionMode.VALIDATE_ONLY)

    assert isinstance(reader, FuturesAccountReader)
    assert isinstance(client, FuturesTradingClient)
    assert reader._position_mode is client._position_mode
