"""`EPIC-045` - `bot add` and `bot delete` reach a running host and run the screen's own New bot and Delete.

@details The owner's rule: whatever the Bots tab does at runtime, the VPS does too. This is the journey on
the composed app over the fake exchange: the operator's `IHostControl` writes a command file into the real
command directory, the host's own `HostedControlPoller` reads it, and the bots change on their own files
while a RUNNING bot beside them keeps its orders. It proves what the unit tests of the handlers cannot: the
two handlers are bound in the composition root and the executor reaches them.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    AUDIT_FILE_NAME,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    FakeExchange,
    booted,
    resting,
)
from .host_control_world import create_grid_bot, ids_of, operator_of, state_of

S = BotLifecycleState


def _add(name: str = "sol grid", venue: str = "spot_testnet", **params: str):  # type: ignore[no-untyped-def]
    return HostControlRequest(
        HostControlAction.ADD,
        ADD_SUBJECT,
        entry=NewBotEntry(
            name,
            "grid",
            venue,
            SYMBOL,
            tuple(ParameterSetting(k, v) for k, v in (params or GRID).items()),
        ),
    )


def _delete(bot_id: str) -> HostControlRequest:
    return HostControlRequest(HostControlAction.DELETE, bot_id)


def test_a_bot_is_added_beside_a_running_one_and_the_running_one_keeps_its_orders(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        running = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)
        started = operator.ask(HostControlRequest(HostControlAction.START, running))
        assert started.status is HostControlStatus.DONE, started.message
        orders_before = dict(resting(app.urls))
        assert orders_before

        added = operator.ask(_add())

        assert added.status is HostControlStatus.DONE, added.message
        new_ids = ids_of(app.store) - {running}
        assert len(new_ids) == 1
        (new_id,) = new_ids
        assert new_id in added.message
        stored = app.store.load(BotId(new_id))
        assert stored.bot.state is S.DRAFT
        assert (stored.bot.definition.name, stored.bot.definition.symbol) == (
            "sol grid",
            SYMBOL,
        )
        assert dict(stored.bot.definition.config) == GRID
        assert state_of(app.store, running) is S.RUNNING
        assert resting(app.urls) == orders_before, "an add places and cancels no order"
        audit = (exchange.tmp_path / "state" / "control" / AUDIT_FILE_NAME).read_text(
            encoding="utf-8"
        )
        assert audit.count('"action": "add"') >= 2  # received + final


def test_an_added_bot_is_started_by_bot_start_alone(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner's procedure: export, scp, `bot add`, `bot start`; no restart."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        added = operator.ask(_add())
        assert added.status is HostControlStatus.DONE, added.message
        (new_id,) = ids_of(app.store)
        assert resting(app.urls) == {}

        started = operator.ask(HostControlRequest(HostControlAction.START, new_id))

        assert started.status is HostControlStatus.DONE, started.message
        assert state_of(app.store, new_id) is S.RUNNING
        assert resting(app.urls)


def test_a_refused_add_creates_nothing_and_a_duplicate_name_points_at_bot_edit(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)

        unreadable = operator.ask(_add(grid_count="many"))
        unknown_venue = operator.ask(_add(venue="spot_nowhere"))
        assert ids_of(app.store) == set()
        first = operator.ask(_add())
        again = operator.ask(_add())

        assert unreadable.status is HostControlStatus.REFUSED
        assert "grid_count is not a whole number" in unreadable.message
        assert unknown_venue.status is HostControlStatus.REFUSED
        assert first.status is HostControlStatus.DONE, first.message
        assert again.status is HostControlStatus.REFUSED
        assert "bot edit" in again.message
        assert len(ids_of(app.store)) == 1


def test_a_draft_is_deleted_and_a_running_bot_is_not(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        draft = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)

        gone = operator.ask(_delete(draft))
        assert gone.status is HostControlStatus.DONE, gone.message
        assert ids_of(app.store) == set()

        running = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)
        operator.ask(HostControlRequest(HostControlAction.START, running))
        orders = dict(resting(app.urls))
        kept = operator.ask(_delete(running))
        assert kept.status is HostControlStatus.REFUSED
        assert "RUNNING" in kept.message and "Nothing was deleted" in kept.message
        assert ids_of(app.store) == {running}
        assert resting(app.urls) == orders, "a refused delete cancels nothing"


def test_a_stopped_bot_that_kept_its_coin_is_kept_and_one_that_sold_it_is_deleted(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real record of a Spot grid stopped with `bot stop` holds the coin it bought at start:
    forgetting it would orphan the coin, so the host keeps the bot. `bot stop --close-position`
    sells the coin, and the same delete then goes through."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        kept_coin = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)
        operator.ask(HostControlRequest(HostControlAction.START, kept_coin))
        stop = HostControlRequest(HostControlAction.STOP, kept_coin)
        assert operator.ask(stop).status is HostControlStatus.DONE
        assert state_of(app.store, kept_coin) is S.STOPPED

        refused = operator.ask(_delete(kept_coin))

        assert refused.status is HostControlStatus.REFUSED
        assert "inventory" in refused.message and "orphan" in refused.message
        assert ids_of(app.store) == {kept_coin}

        # Another bot, stopped with the close from its first run: only dust is left to orphan.
        sold_coin = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)
        # (one active bot per symbol: the first one is deleted in the Bots tab's way, by hand)
        app.store.delete(BotId(kept_coin))
        operator.ask(HostControlRequest(HostControlAction.START, sold_coin))
        sold = operator.ask(
            HostControlRequest(HostControlAction.STOP, sold_coin, close_position=True)
        )
        assert sold.status is HostControlStatus.DONE, sold.message
        assert state_of(app.store, sold_coin) is S.STOPPED
        deleted = operator.ask(_delete(sold_coin))
        assert deleted.status is HostControlStatus.DONE, deleted.message
        assert ids_of(app.store) == set()
        assert resting(app.urls) == {}, (
            "the stop cancelled them; the delete sent nothing"
        )
