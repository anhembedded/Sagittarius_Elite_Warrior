"""`EPIC-039H` (decision O8) - a Stop never keeps a position on a position venue.

@details The choice "keep what the bot holds" is Spot's: the base stays held and the user decides. A
leveraged position left standing has no stop on the exchange yet (`EPIC-039L`), so the Stop use
case refuses the choice in words and queues nothing; closing is always accepted. A Spot bot keeps
its base as before.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
    StopBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.test_bot_lifecycle_commands import (
    _RecordingRunner,
)

_SPOT_PORTS = FakeVenueTradingPorts(fake_venue_ports(TradingVenue.SPOT_TESTNET))
_ID = "abc123"
_CLOCK = FakeBotClock()


def _store_with(venue: TradingVenue) -> FakeBotStore:
    store = FakeBotStore()
    definition = BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"})
    store.save(
        StoredBot(
            Bot(
                BotId(_ID),
                definition,
                BotLifecycle(BotLifecycleState.RUNNING),
                _CLOCK.now(),
            ),
            {"cycles": 1},
        )
    )
    return store


def test_keeping_a_futures_position_is_refused_in_words_and_queues_nothing() -> None:
    store = _store_with(TradingVenue.FUTURES_TESTNET)
    runner = _RecordingRunner(store, _CLOCK)

    result = StopBotCommandHandler(store, runner, _SPOT_PORTS).execute(
        StopBotCommand(_ID, ExposureHandling.KEEP)
    )

    assert result.refusal is BotRefusal.EXPOSURE_MUST_CLOSE
    assert result.message.endswith("Stop and close the position.")
    assert runner.sent == []


def test_closing_a_futures_position_is_accepted() -> None:
    store = _store_with(TradingVenue.FUTURES_TESTNET)
    runner = _RecordingRunner(store, _CLOCK)

    result = StopBotCommandHandler(store, runner, _SPOT_PORTS).execute(
        StopBotCommand(_ID, ExposureHandling.CLOSE_AT_MARKET)
    )

    assert result.accepted
    assert runner.sent == [("stop:CLOSE_AT_MARKET", _ID)]


def test_a_spot_bot_still_keeps_its_base_when_asked() -> None:
    store = _store_with(TradingVenue.SPOT_TESTNET)
    runner = _RecordingRunner(store, _CLOCK)

    result = StopBotCommandHandler(store, runner, _SPOT_PORTS).execute(
        StopBotCommand(_ID, ExposureHandling.KEEP)
    )

    assert result.accepted
    assert runner.sent == [("stop:KEEP", _ID)]


def test_a_stop_for_a_bot_that_does_not_exist_is_the_not_found_refusal() -> None:
    store = FakeBotStore()
    runner = _RecordingRunner(store, _CLOCK)

    result = StopBotCommandHandler(store, runner, _SPOT_PORTS).execute(
        StopBotCommand(_ID, ExposureHandling.KEEP)
    )

    assert result.refusal is BotRefusal.NOT_FOUND
