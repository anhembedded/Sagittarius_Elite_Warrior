"""`BOT-189` (`PRO-015` phase 1) - the owner hears of every filled order, cycle and exit.

@details The composed app over the fake Binance server, with alerting live: a real grid bot on the
Spot Testnet fake, the real alert source, hub, SQLite outbox, Discord lane and `DiscordWebhookChannel`.
Only Discord's HTTP transport and the alert clock are fakes. One message per order that filled whole;
the fill that closes a cycle carries the profit the run booked; a stop loss, a take profit and a price
outside the range are told at once; a restart sends nothing again and tells a fill it missed once;
a read-only copy of the data root sends nothing.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_message import (
    SUPPRESS_NOTIFICATIONS,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.tests.discord_posts import (
    is_heartbeat,
    posts_without_heartbeat,
    wait_until_the_heartbeat_is_told,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from sagittarius_engine.interfaces.i_container import IContainer

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    app_config,
    booted,
)

S = BotLifecycleState
WAIT_S = 15.0
#: How much fake time passes per look at the outbox: more than a paced channel's whole period.
PACING_STEP = timedelta(seconds=2)
WEBHOOK = "https://discord.com/api/webhooks/998877/Sk3l3t0n-T0ken_xyz"
_AT = datetime(2026, 10, 19, 9, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))


@contextmanager
def _told(exchange: FakeExchange) -> Iterator[tuple[BootedApp, FakeWebhookTransport]]:
    """The booted app with Discord's transport faked; what it was sent is on the transport."""
    transport = FakeWebhookTransport()
    clock = FakeAlertClock()
    transport.clock = clock.now

    def prepare(container: IContainer) -> None:
        container.singleton(
            ChannelSecrets,
            ChannelSecrets(InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK})),
        )
        container.singleton(IWebhookTransport, transport)
        container.singleton(IAlertClock, clock)

    with booted(exchange, prepare=prepare) as app:
        yield app, transport


def _settled(app: BootedApp, transport: FakeWebhookTransport) -> list[str]:
    """Every message sent once nothing waits in the outbox; the bots publish on the poster's
    thread, so what is queued by now is all there will be."""
    outbox = app.engine.context.container.resolve(IOutbox)  # type: ignore[type-abstract]
    clock = app.engine.context.container.resolve(IAlertClock)  # type: ignore[type-abstract]
    deadline = time.monotonic() + WAIT_S
    while outbox.backlog(clock.now()).depth > 0:
        assert time.monotonic() < deadline, "the outbox never emptied"
        # Cleared after the wait and the depth read again: a post between a check and a clear
        # must not be a lost wake-up.
        transport.posted.wait(0.05)
        transport.posted.clear()
        # The fake clock stands still, so a channel's own pacing (four messages per two
        # seconds, `EPIC-036C2`) would hold the fifth for ever: the test lets time pass.
        clock.advance(PACING_STEP)
    return [str(post.body["content"]) for post in posts_without_heartbeat(transport)]


def _started(app: BootedApp) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", SPOT, SYMBOL, GRID)
    )
    assert isinstance(created, BotCommandResult) and created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult) and started.accepted, started.message
    return created.bot_id


def _tick(app: BootedApp, price: float) -> None:
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
            market_type=MarketType.SPOT,
            market_data_venue=SPOT.market_data_venue,
        )
    )


def test_one_silent_message_per_full_fill_and_the_cycle_carries_the_profit_booked(
    exchange: FakeExchange,
) -> None:
    with _told(exchange) as (app, transport):
        bot_id = _started(app)
        assert _settled(app, transport) == [], "the opening orders are not ladder fills"

        app.move_price(48700)  # the 48,800 buy fills
        [buy] = _settled(app, transport)

        app.move_price(49700)  # its counter sell fills: one cycle
        [_, sell] = _settled(app, transport)

        runtime = app.runtime(bot_id)
        assert runtime.completed_cycles == 1
        profit = f"{runtime.realised_profit:+,.2f}"

    assert "Order filled: grid" in buy
    assert f"{SYMBOL} · BUY" in buy
    assert "@ 48,800" in buy and "(level 1)" in buy
    assert "cycle" not in buy
    assert f"{SYMBOL} · SELL" in sell and "(level 2)" in sell
    assert f"cycle {profit} USDT · grid profit {profit} USDT · 1 cycle" in sell
    assert [post.body["flags"] for post in posts_without_heartbeat(transport)] == [
        SUPPRESS_NOTIFICATIONS
    ] * 2


def test_the_apps_own_heartbeat_is_not_counted_among_the_messages_a_bot_earns(
    exchange: FakeExchange,
) -> None:
    """`BUG-252`: a run that lasts a second gets a heartbeat beside the bot's fill, and every
    journey here that counts what was sent failed on a slow runner. The wait makes that certain."""
    with _told(exchange) as (app, transport):
        _started(app)
        app.move_price(48700)
        wait_until_the_heartbeat_is_told(
            transport, app.engine.context.container.resolve(IAlertClock)
        )  # type: ignore[type-abstract]

        [buy] = _settled(app, transport)

    assert any(is_heartbeat(post) for post in transport.posts), "no heartbeat was told"
    assert "Order filled: grid" in buy and f"{SYMBOL} · BUY" in buy
    assert [post.body["flags"] for post in posts_without_heartbeat(transport)] == [
        SUPPRESS_NOTIFICATIONS
    ]


def test_a_restart_sends_nothing_again_and_tells_a_fill_missed_while_closed_once(
    exchange: FakeExchange,
) -> None:
    with _told(exchange) as (first, first_transport):
        bot_id = _started(first)
        first.move_price(48700)
        [told_before] = _settled(first, first_transport)
    assert "BUY" in told_before

    # The app is closed: the buy's counter sell fills while nobody listens.
    exchange.urls.spot_account.set_last_price(SYMBOL, Decimal(49700))
    exchange.urls.spot_account.drain_user_data_events()

    with _told(exchange) as (second, second_transport):
        assert second.bot(bot_id).state is S.RECOVERING
        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=SPOT)
        )

        [missed] = _settled(second, second_transport)

        assert second.bot(bot_id).state is S.RUNNING
    assert f"{SYMBOL} · SELL" in missed and "cycle" in missed
    assert "BUY" not in missed


@pytest.mark.parametrize(
    ("price", "title", "severity"),
    [
        (39_000.0, "Stop loss hit: grid", "CRITICAL"),
        (61_000.0, "Take profit hit: grid", "CRITICAL"),
    ],
)
def test_a_stop_loss_and_a_take_profit_are_told_once_and_loud_not_as_fills(
    exchange: FakeExchange, price: float, title: str, severity: str
) -> None:
    with _told(exchange) as (app, transport):
        bot_id = _started(app)

        _tick(app, price)
        messages = _settled(app, transport)

        assert app.bot(bot_id).state in (S.STOPPING, S.STOPPED)
    # The stop sits outside the range, so the same tick also leaves the range: that WARNING is
    # the range exit's own message, and no fill message is among them.
    [message] = [m for m in messages if title in m]
    assert severity in message
    assert "closing its position at market" in message
    assert not [m for m in messages if "Order filled" in m]
    assert all(
        "flags" not in post.body for post in transport.posts if title in str(post.body)
    )


def test_a_bot_set_to_critical_only_sends_no_fill_and_still_sends_its_stop_loss(
    exchange: FakeExchange,
) -> None:
    """`BOT-191`: the owner's choice, kept by the real settings file, reaches the hub."""
    with _told(exchange) as (app, transport):
        bot_id = _started(app)
        modes = app.engine.context.container.resolve(IBotAlertModes)  # type: ignore[type-abstract]
        modes.set_mode(bot_id, BotAlertMode.CRITICAL_ONLY)

        app.move_price(48700)  # the 48,800 buy fills: a fill message, were it on
        assert _settled(app, transport) == []

        _tick(app, 39_000.0)
        messages = _settled(app, transport)

    assert [m for m in messages if "Stop loss hit: grid" in m]
    assert not [m for m in messages if "Order filled" in m]


def test_the_choice_survives_a_restart_of_the_app(exchange: FakeExchange) -> None:
    with _told(exchange) as (first, _transport):
        bot_id = _started(first)
        modes = first.engine.context.container.resolve(IBotAlertModes)  # type: ignore[type-abstract]
        modes.set_mode(bot_id, BotAlertMode.OFF)

    with _told(exchange) as (second, _transport):
        settings = second.engine.context.container.resolve(IAlertSettingsSource)  # type: ignore[type-abstract]
        assert settings.current().mode_of(bot_id) is BotAlertMode.OFF


def test_a_price_outside_the_range_is_told_once_while_it_stays_out_and_not_again_on_a_flap(
    exchange: FakeExchange,
) -> None:
    with _told(exchange) as (app, transport):
        _started(app)

        _tick(app, 47_000.0)
        [left] = _settled(app, transport)
        _tick(app, 46_000.0)
        assert _settled(app, transport) == [left]
        _tick(app, 50_000.0)  # back inside: not told
        _tick(app, 47_000.0)  # out again inside the window: the same condition
        assert _settled(app, transport) == [left]

    assert "WARNING" in left and "Price left the range: grid" in left
    assert "below the range 48000-52000" in left and "keeps its orders" in left


def test_a_read_only_copy_sends_nothing_for_a_fill(
    exchange: FakeExchange, tmp_path: Path
) -> None:
    """A second copy on the same data root is read-only: the module subscribes nothing there."""
    transport = FakeWebhookTransport()
    lock = tmp_path / "state" / "instance.lock"
    first = InstanceAccess.acquire(lock)
    second = InstanceAccess.acquire(lock)
    assert second.read_only is True
    app = create_app(app_config(tmp_path), second)
    app.container.singleton(
        ChannelSecrets,
        ChannelSecrets(InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK})),
    )
    app.container.singleton(IWebhookTransport, transport)
    app.boot()
    try:
        app.event_bus.emit(
            BotOrderFilledEvent(
                bot_id="abc123",
                order_id="o-1",
                side="BUY",
                price=Decimal(48800),
                quantity=Decimal(1),
                level=1,
                grid_profit=Decimal(0),
                completed_cycles=0,
                quote_asset="USDT",
            )
        )
    finally:
        app.stop()
        first.release()

    assert transport.posts == []
    assert not (tmp_path / "state" / "alerts.sqlite3").exists()
