"""`EPIC-038L` - `bot edit` reaches a running host and runs the screen's own Save for one bot at rest.

@details The owner's incident: `bot start` was refused because the range no longer held the price, and
`bot apply` could not correct it because the running host holds the data root. This is the journey on
the composed app over the fake exchange, for Spot and for Futures: the operator's `IHostControl` writes
a command file into the real command directory, the host's own `HostedControlPoller` reads it, and the
bot's parameters change on the bot's own file, with the host (and its order session) untouched.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .futures_bots_world import GRID as FUTURES_GRID
from .futures_bots_world import booted_futures_bots
from .futures_fake_exchange import FUTURES
from .futures_fake_exchange import SYMBOL as FUTURES_SYMBOL
from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    FakeExchange,
    booted,
)
from .host_control_world import create_grid_bot, operator_of, state_of

S = BotLifecycleState


def _edit(bot_id: str, **settings: str) -> HostControlRequest:
    return HostControlRequest(
        HostControlAction.EDIT,
        bot_id,
        settings=tuple(ParameterSetting(k, v) for k, v in settings.items()),
    )


def test_a_stopped_spot_bot_is_edited_and_started_again_while_the_host_keeps_running(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner's case: Stop, edit, Start of ONE bot, with no restart of the host."""
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        bot_id = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)
        assert (
            operator.ask(HostControlRequest(HostControlAction.START, bot_id)).status
            is HostControlStatus.DONE
        )

        refused = operator.ask(_edit(bot_id, lower="47000"))
        assert refused.status is HostControlStatus.REFUSED
        assert "RUNNING" in refused.message and "DRAFT or STOPPED" in refused.message
        assert app.store.load(BotId(bot_id)).bot.definition.config["lower"] == "48000"
        assert state_of(app.store, bot_id) is S.RUNNING

        stopped = operator.ask(HostControlRequest(HostControlAction.STOP, bot_id))
        assert stopped.status is HostControlStatus.DONE, stopped.message
        assert state_of(app.store, bot_id) is S.STOPPED

        edited = operator.ask(_edit(bot_id, lower="47000", grid_count="6"))
        assert edited.status is HostControlStatus.DONE, edited.message
        assert "lower 48000 -> 47000" in edited.message
        assert "grid_count 5 -> 6" in edited.message
        config = app.store.load(BotId(bot_id)).bot.definition.config
        assert (config["lower"], config["grid_count"]) == ("47000", "6")
        assert state_of(app.store, bot_id) is S.DRAFT

        again = operator.ask(HostControlRequest(HostControlAction.START, bot_id))
        assert again.status is HostControlStatus.DONE, again.message
        assert state_of(app.store, bot_id) is S.RUNNING
        audit = (exchange.tmp_path / "state" / "control" / AUDIT_FILE_NAME).read_text(
            encoding="utf-8"
        )
        assert audit.count('"action": "edit"') >= 4  # received + final, twice


def test_an_unknown_parameter_and_an_unreadable_value_are_refused_and_change_nothing(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        bot_id = create_grid_bot(app.engine, SPOT, SYMBOL, GRID)

        unknown = operator.ask(_edit(bot_id, lowr="47000"))
        unreadable = operator.ask(_edit(bot_id, grid_count="many"))

        assert unknown.status is HostControlStatus.REFUSED
        assert "lowr" in unknown.message
        assert unreadable.status is HostControlStatus.REFUSED
        assert "grid_count is not a whole number" in unreadable.message
        assert dict(app.store.load(BotId(bot_id)).bot.definition.config) == GRID
        assert state_of(app.store, bot_id) is S.DRAFT


def test_a_futures_bot_changes_its_leverage_and_a_mainnet_one_needs_no_typed_venue(
    futures: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(futures.tmp_path))
    with booted_futures_bots(futures) as app:
        operator = operator_of(app.engine, futures.tmp_path, app.deliver)
        testnet = create_grid_bot(app.engine, FUTURES, FUTURES_SYMBOL, FUTURES_GRID)
        mainnet = create_grid_bot(
            app.engine, TradingVenue.FUTURES_MAINNET, FUTURES_SYMBOL, FUTURES_GRID
        )

        on_testnet = operator.ask(_edit(testnet, leverage="5"))
        on_mainnet = operator.ask(_edit(mainnet, leverage="2", lower="61000"))

        assert on_testnet.status is HostControlStatus.DONE, on_testnet.message
        assert "leverage 3 -> 5" in on_testnet.message
        assert on_mainnet.status is HostControlStatus.DONE, on_mainnet.message
        config = app.store.load(BotId(mainnet)).bot.definition.config
        assert (config["leverage"], config["lower"]) == ("2", "61000")
        assert app.resting() == {}, "an edit places no order"
