"""`EPIC-045G` - `bot move` reaches a running host and runs the screen's own Venue field for one DRAFT.

@details The journey on the composed app over the fake exchange: the operator's `IHostControl` writes a command
file into the real command directory, the host's own `HostedControlPoller` reads it, and the bot's file changes
venue, with its id and parameters kept, no order placed and the real-money question at `bot start` untouched
(it is still refused without the typed venue). It also proves the handler is bound in the composition root.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .grid_fake_exchange import GRID, SPOT, SYMBOL, FakeExchange, booted, resting
from .host_control_world import create_grid_bot, ids_of, operator_of, state_of

S = BotLifecycleState


def _move(bot_id: str, venue: str) -> HostControlRequest:
    return HostControlRequest(HostControlAction.MOVE, bot_id, to_venue=venue)


def test_a_draft_is_moved_to_mainnet_keeping_its_id_and_the_start_still_needs_the_typed_venue(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        bot_id = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)

        moved = operator.ask(_move(bot_id, "spot_mainnet"))

        assert moved.status is HostControlStatus.DONE, moved.message
        stored = app.store.load(BotId(bot_id)).bot
        assert stored.definition.venue is TradingVenue.SPOT_MAINNET
        assert dict(stored.definition.config) == GRID
        assert ids_of(app.store) == {bot_id}
        assert state_of(app.store, bot_id) is S.DRAFT
        assert resting(app.urls) == {}, "a move places no order"
        refused = operator.ask(HostControlRequest(HostControlAction.START, bot_id))
        assert refused.status is HostControlStatus.REFUSED
        assert "spot_mainnet" in refused.message
        assert state_of(app.store, bot_id) is S.DRAFT, "nothing started unconfirmed"


def test_a_bot_that_is_running_does_not_move_and_keeps_its_orders(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        bot_id = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)
        operator.ask(HostControlRequest(HostControlAction.START, bot_id))
        orders = dict(resting(app.urls))

        refused = operator.ask(_move(bot_id, "spot_mainnet"))

        assert refused.status is HostControlStatus.REFUSED
        assert "Nothing was moved" in refused.message
        assert (
            app.store.load(BotId(bot_id)).bot.definition.venue
            is TradingVenue.SPOT_TESTNET
        )
        assert resting(app.urls) == orders


def test_a_venue_the_build_does_not_have_is_refused_and_changes_nothing(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        bot_id = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)

        refused = operator.ask(_move(bot_id, "spot_nowhere"))

        assert refused.status is HostControlStatus.REFUSED
        assert "not a venue" in refused.message
        assert (
            app.store.load(BotId(bot_id)).bot.definition.venue
            is TradingVenue.SPOT_TESTNET
        )
