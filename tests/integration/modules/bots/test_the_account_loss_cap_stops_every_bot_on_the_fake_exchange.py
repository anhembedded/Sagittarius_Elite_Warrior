"""`EPIC-026L` - the account-level loss cap, on the composed app over the fake exchange (decision N3).

@details A Spot bot and a Futures bot run together, as they would on one host. Their prices fall;
the cap, sampled on the bots ticker the app wires (`FakeBotTicker.fire` is one tick), adds up what
the two have lost today. Below the owner's figure nothing happens. At it, every bot is stopped by
the Bots tab's own Stop (the Spot bot keeps its coin, the Futures bot closes its position), the
owner's alert event is published once, and no bot starts again: not now, not after a restart, until
the owner acknowledges through the host's command directory. Only the network, the websocket and
the bots' queue and pacer are substituted (`two_venues_bots_world`).

A bot's file keeps the last price it heard at most every `MARK_PRICE_SAVE_SECONDS`, so a tick
here is preceded by that much machine time, as it is in life.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    LOSS_CAP_SUBJECT,
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_price_reaction import (
    MARK_PRICE_SAVE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.account_loss_cap import (
    AccountLossCap,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.account_loss_cap_tripped_event import (
    AccountLossCapTrippedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_figure import (
    LossCapFigureError,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    AUDIT_FILE_NAME,
    control_directory_of,
    prepare_private_directory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_control import (
    DirectoryHostControl,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.hosted_control_poller import (
    HostedControlPoller,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.jsonl_host_control_audit import (
    JsonlHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .grid_fake_exchange import BASELINE, FakeExchange
from .test_bots_on_two_venues_run_together_on_the_fake_exchange import _both_running
from .two_venues_bots_world import (
    FUTURES,
    SPOT,
    SYMBOL,
    BootedTwoVenues,
    booted_two_venues,
)

S = BotLifecycleState
#: The two bots' losses at the prices below, measured on the fake exchange: about 56 USDT at the
#: first fall and about 145 USDT at the second. 120 sits between them.
FIGURE = "120 USDT"
_AT = datetime(2026, 10, 20, 9, tzinfo=UTC)


def _tick(app: BootedTwoVenues, venue: TradingVenue, price: int) -> None:
    """What the venue's kline websocket publishes for a trade at `price`."""
    app.engine.event_bus.emit(
        MarketTickEvent(
            MarketData(
                symbol=SYMBOL,
                interval="1m",
                open_time=_AT,
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=1.0,
                close_time=_AT,
                quote_asset_volume=1.0,
                number_of_trades=1,
                taker_buy_base_asset_volume=1.0,
                taker_buy_quote_asset_volume=1.0,
            ),
            market_type=(
                MarketType.SPOT if venue is SPOT else MarketType.FUTURES_USD_M
            ),
            market_data_venue=venue.market_data_venue,
        )
    )


def _prices_fall_to(app: BootedTwoVenues, spot: int, futures: int) -> None:
    """Each bot hears its price and saves it to its file, as it does at most every half minute."""
    app.monotonic.advance(MARK_PRICE_SAVE_SECONDS + 1)
    _tick(app, SPOT, spot)
    _tick(app, FUTURES, futures)


def _trips(app: BootedTwoVenues) -> list[AccountLossCapTrippedEvent]:
    heard: list[AccountLossCapTrippedEvent] = []
    app.engine.event_bus.on(AccountLossCapTrippedEvent, heard.append)
    return heard


def _start(app: BootedTwoVenues, bot_id: str) -> BotCommandResult:
    answer = app.engine.dispatch(
        StartBotCommand, StartBotCommand(bot_id, real_money_confirmed=True)
    )
    assert isinstance(answer, BotCommandResult)
    return answer


def _record_path(exchange: FakeExchange) -> Path:
    return exchange.tmp_path / "loss_cap.json"


class _HostHoldsTheLock(IInstanceProbe):
    def is_held(self) -> bool:
        return True


def _operator(
    app: BootedTwoVenues, directory: Path, command_id: str
) -> DirectoryHostControl:
    """The owner's writer; its sleep is the host's turn (it polls its command directory)."""
    container = app.engine.context.container
    host = container.resolve(HostedControlPoller)
    clock_s = [0.0]

    def the_host_gets_a_turn(seconds: float) -> None:
        clock_s[0] += seconds
        host.poll_once()
        app.deliver()

    return DirectoryHostControl(
        directory,
        _HostHoldsTheLock(),
        JsonlHostControlAudit(directory / AUDIT_FILE_NAME),
        container.resolve(IOperationsClock),
        lambda: command_id,
        the_host_gets_a_turn,
        lambda: clock_s[0],
    )


def _trip_the_cap(
    app: BootedTwoVenues, running: tuple[str, str] | None = None
) -> tuple[str, str]:
    spot, futures = running or _both_running(app)
    _prices_fall_to(app, 48500, 62500)
    app.ticker.fire()
    assert (app.bot(spot).state, app.bot(futures).state) == (S.RUNNING, S.RUNNING)
    _prices_fall_to(app, 46000, 60000)
    app.ticker.fire()
    return spot, futures


def test_below_the_figure_nothing_is_stopped(both_venues: FakeExchange) -> None:
    with booted_two_venues(both_venues, loss_cap=FIGURE) as app:
        spot, futures = _both_running(app)
        trips = _trips(app)

        _prices_fall_to(app, 48500, 62500)
        app.ticker.fire()

        assert (app.bot(spot).state, app.bot(futures).state) == (S.RUNNING, S.RUNNING)
        assert trips == []
        status = app.engine.container.resolve(AccountLossCap).status()
        assert not status.tripped and Decimal(-120) < status.day_pnl < Decimal(-20)


def test_at_the_figure_every_bot_is_stopped_through_the_stop_and_the_owner_is_told_once(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues, loss_cap=FIGURE) as app:
        trips = _trips(app)
        running = _both_running(app)
        assert (
            app.client(FUTURES).get_positions() != []
        )  # the Futures bot holds a position

        spot, futures = _trip_the_cap(app, running)
        app.ticker.fire()

        assert (app.bot(spot).state, app.bot(futures).state) == (S.STOPPED, S.STOPPED)
        assert app.resting(SPOT) == set() and app.resting(FUTURES) == set()
        # The Spot stop keeps the coin; the Futures stop (the only form it accepts) closes the position.
        assert app.exchange.urls.spot_account.free_balance("BTC") > BASELINE["BTC"]
        assert (
            app.client(FUTURES).get_positions() == []
        )  # a flat position is simply absent
        [event] = trips
        assert event.reason == "loss_reached" and event.figure == FIGURE
        assert event.bots_stopped == 2 and Decimal(event.loss) >= Decimal(120)


def test_a_tripped_cap_refuses_every_start_in_the_owners_words_and_survives_a_restart(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues, loss_cap=FIGURE) as app:
        spot, _futures = _trip_the_cap(app)
        refused = _start(app, spot)
        assert refused.refusal is BotRefusal.LOSS_CAP_TRIPPED
        assert "loss-cap-ack" in refused.message
        assert app.bot(spot).state is S.STOPPED
    assert '"reason": "loss_reached"' in _record_path(both_venues).read_text(
        encoding="utf-8"
    )

    with booted_two_venues(both_venues, loss_cap=FIGURE, open_sessions=False) as again:
        assert again.engine.container.resolve(AccountLossCap).status().tripped
        assert _start(again, spot).refusal is BotRefusal.LOSS_CAP_TRIPPED
        assert again.bot(spot).state is S.STOPPED


def test_the_owner_acknowledges_through_the_command_directory_and_only_then_may_a_bot_start(
    both_venues: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(both_venues.tmp_path))
    with booted_two_venues(both_venues, loss_cap=FIGURE) as app:
        spot, _futures = _trip_the_cap(app)
    with booted_two_venues(both_venues, loss_cap=FIGURE, open_sessions=False) as app:
        directory = control_directory_of(both_venues.tmp_path / "state")
        assert prepare_private_directory(directory) == ""
        ack = HostControlRequest(
            HostControlAction.ACKNOWLEDGE_LOSS_CAP, LOSS_CAP_SUBJECT
        )

        reply = _operator(app, directory, "a" * 32).send(ack, 15.0)

        assert reply.status is HostControlStatus.DONE, reply.message
        assert not app.engine.container.resolve(AccountLossCap).status().tripped
        assert app.bot(spot).state is S.STOPPED  # acknowledging starts nothing
        again = _operator(app, directory, "b" * 32).send(ack, 15.0)
        assert again.status is HostControlStatus.REFUSED
        assert _start(app, spot).accepted
        assert app.bot(spot).state in (S.STARTING, S.RUNNING)
    with booted_two_venues(both_venues, loss_cap=FIGURE, open_sessions=False) as app:
        assert not app.engine.container.resolve(AccountLossCap).status().tripped


def test_with_no_figure_the_cap_is_off_and_a_large_loss_stops_nothing(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        spot, futures = _both_running(app)
        trips = _trips(app)

        _prices_fall_to(app, 46000, 60000)
        app.ticker.fire()

        assert (app.bot(spot).state, app.bot(futures).state) == (S.RUNNING, S.RUNNING)
        assert trips == []
        assert app.engine.container.resolve(AccountLossCap).status().figure is None
        assert not _record_path(both_venues).exists()


def test_a_figure_that_is_set_and_unreadable_stops_the_app_from_booting_with_the_cap_unarmed(
    both_venues: FakeExchange,
) -> None:
    with (
        pytest.raises(LossCapFigureError, match="amount and its quote asset"),
        booted_two_venues(both_venues, loss_cap="five hundred"),
    ):
        pytest.fail("the app must not boot with a cap the owner thinks is on")
