"""`run --resume-recovering`: the host opens the order session the GUI opens (`EPIC-038D`, decision O2).

A restart leaves RUNNING and PAUSED bots RECOVERING until a deliberate action opens the
venue's order session - that action reconciles every bot on the venue against the
exchange (`BotEventRouter.on_switch`). The host's request is that action, nothing
else: it asks `ITradingSession.ensure_ready()` for each venue that holds a RECOVERING
bot, and for a mainnet venue only when the operator typed it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_recovering_for_host import (
    ResumeRecoveringForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeRecoveringForHostCommand,
    ResumeRecoveringResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SPOT_TESTNET = TradingVenue.SPOT_TESTNET
FUTURES_TESTNET = TradingVenue.FUTURES_TESTNET
SPOT_MAINNET = TradingVenue.SPOT_MAINNET

_OPEN = SessionReadyResult(
    ready=True, block_reason=None, reconciled_positions=(), reconciled_open_orders=()
)
_REFUSED = SessionReadyResult(
    ready=False,
    block_reason=SessionBlockReason.UNEXPECTED_POSITIONS,
    reconciled_positions=(),
    reconciled_open_orders=(),
)


def _bot(
    store: FakeBotStore, bot_id: str, venue: TradingVenue, state: BotLifecycleState
) -> None:
    bot = Bot(
        BotId(bot_id),
        BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"}),
        BotLifecycle(state),
        FAKE_CLOCK_START,
    )
    store.save(StoredBot(bot, {}))


class _World:
    def __init__(self, *venues: TradingVenue) -> None:
        self.sessions = {v: FakeTradingSession() for v in venues}
        for session in self.sessions.values():
            session.ready_answers(_OPEN)
        self.ports = FakeVenueTradingPorts(
            *(fake_venue_ports(v, trading_session=s) for v, s in self.sessions.items())
        )
        self.store = FakeBotStore()

    def resume(self, confirmed: str | None = None) -> ResumeRecoveringResult:
        handler = ResumeRecoveringForHostCommandHandler(self.store, self.ports)
        return handler.execute(ResumeRecoveringForHostCommand(confirmed))

    def asked(self) -> dict[str, int]:
        return {v.value: s.ready_requests for v, s in self.sessions.items()}


def test_each_venue_with_a_recovering_bot_is_asked_once_to_open_its_session() -> None:
    world = _World(SPOT_TESTNET, FUTURES_TESTNET)
    _bot(world.store, "aaaaaa", SPOT_TESTNET, BotLifecycleState.RECOVERING)
    _bot(world.store, "bbbbbb", SPOT_TESTNET, BotLifecycleState.RECOVERING)

    result = world.resume()

    assert world.asked() == {"spot_testnet": 1, "futures_testnet": 0}
    assert [(v.venue, v.opened) for v in result.venues] == [("spot_testnet", True)]
    assert result.venues[0].bot_ids == ("aaaaaa", "bbbbbb")


def test_a_venue_whose_bots_are_not_recovering_is_not_touched() -> None:
    world = _World(SPOT_TESTNET)
    _bot(world.store, "aaaaaa", SPOT_TESTNET, BotLifecycleState.RUNNING)
    _bot(world.store, "bbbbbb", SPOT_TESTNET, BotLifecycleState.HALTED)
    _bot(world.store, "cccccc", SPOT_TESTNET, BotLifecycleState.STOPPED)

    result = world.resume()

    assert world.asked() == {"spot_testnet": 0}
    assert result.venues == ()


def test_a_session_the_exchange_refuses_is_reported_with_its_reason_not_hidden() -> (
    None
):
    world = _World(SPOT_TESTNET)
    world.sessions[SPOT_TESTNET].ready_answers(_REFUSED)
    _bot(world.store, "aaaaaa", SPOT_TESTNET, BotLifecycleState.RECOVERING)

    (venue,) = world.resume().venues

    assert venue.opened is False
    assert "unexpected open positions" in venue.note


def test_a_mainnet_venue_is_opened_only_when_the_operator_typed_it() -> None:
    world = _World(SPOT_MAINNET)
    _bot(world.store, "aaaaaa", SPOT_MAINNET, BotLifecycleState.RECOVERING)

    refused = world.resume()
    assert world.asked() == {"spot_mainnet": 0}
    assert refused.venues[0].opened is False
    assert "--confirm-venue spot_mainnet" in refused.venues[0].note

    world.resume(confirmed="spot_testnet")
    assert world.asked() == {"spot_mainnet": 0}  # another venue typed

    opened = world.resume(confirmed="spot_mainnet")
    assert world.asked() == {"spot_mainnet": 1}
    assert opened.venues[0].opened is True


def test_the_hosts_resume_recovering_opens_the_session_for_no_one_bot() -> None:
    """`BOT-183`: it exists to wake every RECOVERING bot of the venue, so its opening names none."""
    world = _World(SPOT_TESTNET)
    _bot(world.store, "aaaaaa", SPOT_TESTNET, BotLifecycleState.RECOVERING)

    world.resume()

    assert world.sessions[SPOT_TESTNET].opened_for == [None]
