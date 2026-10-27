"""`EPIC-047H` - the composed host over the fake exchange serves the VPS tab its data, only by reading, inside its ceiling.

The chain is the app's own: the bus the bots' price streams publish on, the module's `boot()`, the scheduler jobs,
the refresher's worker, the bots' real readers, the venue's real session, call policy and gate, and the fake
exchange, which charges each request the weight Binance documents. What a unit test of the refresher cannot show:
the market-data file follows a real `MarketTickEvent` and a real mark read; an asked-for refresh reaches the exchange
through the real readers, as reads only, within 3 % of the minute's weight, and fills the host-reads file and the
facts file; and past the 70 % line the refresh sends nothing while the reads that guard an exit are still served.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    IBotReadRefresh,
    RefreshScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.wire_roots import (
    OPERATIONS_WIRE_ROOTS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HOST_FACTS_FILE_NAME,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_reads_document import (
    HOST_READS_FILE_NAME,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_facts_refresh_requests import (
    IFactsRefreshRequests,
    RefreshRequestVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    MARKET_DATA_FILE_NAME,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

from .grid_fake_exchange import FakeExchange
from .two_venues_bots_world import (
    FUTURES,
    GRIDS,
    SYMBOL,
    BootedTwoVenues,
    booted_two_venues,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.request_weight import WeightMeter

ROOTS = WireRoots(OPERATIONS_WIRE_ROOTS)
WITHIN_S = 8.0
LIMIT = 2400
SOFT_LINE = int(LIMIT * 0.7)
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def _seed(
    app: BootedTwoVenues, state: BotLifecycleState = BotLifecycleState.STOPPED
) -> str:
    definition = BotDefinition("paper", "grid", FUTURES, SYMBOL, GRIDS[FUTURES])
    app.store.save(
        StoredBot(Bot(BotId("fff000"), definition, BotLifecycle(state), NOW))
    )
    return "fff000"


def _file(name: str) -> object:
    path = data_root() / "state" / name
    return ROOTS.decode(json.loads(path.read_bytes())) if path.exists() else None


def _wait_for(what: str, condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + WITHIN_S
    while time.monotonic() < deadline:
        if condition():
            return
        threading.Event().wait(0.05)
    pytest.fail(f"within {WITHIN_S:g} s: {what}")


def _tick(price: float) -> MarketTickEvent:
    return MarketTickEvent(
        MarketData(
            SYMBOL,
            "1m",
            NOW,
            price,
            price + 1,
            price - 1,
            price,
            2.0,
            NOW + timedelta(seconds=59),
            0.0,
            0,
            0.0,
            0.0,
            is_closed=False,
        ),
        market_type=FUTURES.market_type,  # type: ignore[arg-type]
        market_data_venue=FUTURES.market_data_venue,
    )


def test_a_tick_on_the_bus_and_a_mark_the_exit_watch_reads_reach_the_market_data_file(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as app:
        container = app.engine.context.container

        container.resolve(IEventPublisher).publish(_tick(50123.5))
        container.resolve(IVenueTradingPorts).get(
            FUTURES
        ).order_entry_terms.mark_price_for(SYMBOL)

        def published() -> bool:
            document = _file(MARKET_DATA_FILE_NAME)
            symbols = getattr(document, "symbols", ())
            return any(
                s.venue is FUTURES
                and s.last_price == Decimal("50123.5")
                and s.mark_price is not None
                for s in symbols
            )

        _wait_for("the market-data file shows the tick and the mark", published)
        (market,) = [
            s for s in _file(MARKET_DATA_FILE_NAME).symbols if s.venue is FUTURES
        ]  # type: ignore[attr-defined]
        assert [c.timeframe for c in market.forming] == ["1m", "5m", "15m", "1h", "1d"]
        assert market.last_at is not None
        assert (
            data_root() / "state" / MARKET_DATA_FILE_NAME
        ).stat().st_mode & 0o077 == 0


def _asked_round(app: BootedTwoVenues) -> tuple[str, IFactsRefreshRequests]:
    bot_id = _seed(app)
    requests = app.engine.context.container.resolve(IFactsRefreshRequests)
    _wait_for(
        "the worker has seen the bot",
        lambda: (
            requests.request(bot_id).verdict is not RefreshRequestVerdict.UNKNOWN_BOT
        ),
    )
    return bot_id, requests


def test_an_asked_for_refresh_reaches_the_exchange_through_the_real_readers_as_reads_only(
    both_venues: FakeExchange,
) -> None:
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        bot_id, requests = _asked_round(app)
        mark = meter.mark()

        assert requests.request(bot_id).verdict is RefreshRequestVerdict.QUEUED

        def bot_facts_read() -> bool:
            path = data_root() / "state" / HOST_FACTS_FILE_NAME
            reads = (
                json.loads(path.read_bytes())["exchange_reads"] if path.exists() else []
            )
            return any(row["bot_id"] == bot_id for row in reads)

        _wait_for("the host-facts file shows the bot's exchange read", bot_facts_read)
        spent = meter.since(mark)
        assert spent, "the worker read the exchange"
        assert {r.method for r in spent} == {"GET"}, (
            "a refresh reads and does nothing else"
        )
        assert "GET /fapi/v3/positionRisk" in {f"{r.method} {r.path}" for r in spent}


def test_what_the_readers_read_is_published_in_the_reads_file_with_the_time_it_was_read(
    both_venues: FakeExchange,
) -> None:
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        bot_id = _seed(app)
        refresh = app.engine.context.container.resolve(IBotReadRefresh)
        mark = meter.mark()

        outcomes = [refresh.refresh(bot_id, scope) for scope in RefreshScope]

        def published() -> bool:
            reads = getattr(_file(HOST_READS_FILE_NAME), "reads", None)
            return reads is not None and bool(reads.planner) and bool(reads.fills)

        _wait_for(
            "the host-reads file holds the planner inputs and the fills", published
        )
        reads = _file(HOST_READS_FILE_NAME).reads  # type: ignore[attr-defined]
        assert all(o.read_at is not None for o in outcomes)
        assert (reads.planner[0].bot_id, reads.fills[0].bot_id) == (bot_id, bot_id)
        assert reads.planner[0].read_at == outcomes[1].read_at
        assert {r.method for r in meter.since(mark)} == {"GET"}


def test_past_the_soft_line_the_refresh_sends_nothing_while_the_exit_guards_still_read(
    both_venues: FakeExchange,
) -> None:
    meter: WeightMeter = both_venues.urls.weights
    meter.use_clock(lambda: 0.0)
    with booted_two_venues(both_venues) as app:
        container = app.engine.context.container
        bot_id = _seed(app)
        ports = container.resolve(IVenueTradingPorts).get(FUTURES)
        while meter.charge("GET", "/fapi/v1/openOrders", {}) < SOFT_LINE + 20:
            pass
        ports.account_snapshot.open_positions(
            RequestPriority.EXIT_GUARD
        )  # its answer reports the weight
        mark = meter.mark()

        outcomes = [
            container.resolve(IBotReadRefresh).refresh(bot_id, scope)
            for scope in RefreshScope
        ]
        refused_sent = meter.since(mark)
        mark = meter.mark()
        ports.account_snapshot.open_positions(RequestPriority.EXIT_GUARD)
        ports.order_entry_terms.mark_price_for(SYMBOL, RequestPriority.EXIT_GUARD)

        assert [o.read_at for o in outcomes] == [None] * len(RefreshScope)
        assert refused_sent == (), (
            "a routine read waits at the 70 % line and is not sent"
        )
        assert {f"{r.method} {r.path}" for r in meter.since(mark)} >= {
            "GET /fapi/v3/positionRisk",
            "GET /fapi/v1/premiumIndex",
        }, "the reads that guard an exit are still served"
