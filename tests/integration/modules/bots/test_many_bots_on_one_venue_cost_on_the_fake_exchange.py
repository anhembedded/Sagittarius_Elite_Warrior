"""`EPIC-029J` J1b - what N bots on one venue cost: tick fan-out and request weight, measured.

@details The numbers behind the cap (`MAX_ACTIVE_BOTS_PER_VENUE`), taken on the composed app over
the fake exchange. Run `pytest -k measured` to see them (each is written on the terminal). They are recorded in
`Tasks/epics/EPIC-029_bots_tab_grid_fast_track/incomplete/EPIC-029J1b_many_bots_on_one_venue.md`
§5a, with what each one means.

Two kinds of test live here. The *measured* ones print a figure and assert only a bound derived
from the exchange's own limit (Futures: 2,400 weight a minute, the gate closing at 70 %), never a
wall-clock time. The *structural* ones assert what must hold at any N: a tick reaches the bots of
its own symbol and no other, and the gate keeps a start burst under the exchange's limit.

Weight is the Futures fake's (`WeightMeter`): the Binance weights of `request_weight.py`. The
gate's 70 % line is lifted for the measurements that ask what N bots *would* spend, so the figure
is not cut off by the gate; the gate itself is tested unlifted in the last test.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle import (
    other_active_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    CHECK_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.venue_bot_cap import (
    MAX_ACTIVE_BOTS_PER_VENUE,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance import (
    exchange_call_policy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)

from .crowd_bots_world import FUTURES_SYMBOLS, create_bot, run_bots, start_bot
from .grid_fake_exchange import FakeExchange
from .two_venues_bots_world import FUTURES, BootedTwoVenues, booted_two_venues

S = BotLifecycleState
COUNTS = (1, 5, 20)
#: Binance's per-minute weight for a Futures IP and the share at which the app's gate closes.
FUTURES_WEIGHT = 2400
GATE_LINE = int(FUTURES_WEIGHT * exchange_call_policy.SOFT_WEIGHT_RATIO)
#: What the cap was sized with (`EPIC-029J1b` §5a): an idle Futures bot's minute, measured 175
#: weight (the risk watch's two position reads and two mark reads a beat), with 5 % to spare.
IDLE_WEIGHT_PER_BOT_BUDGET = 185
TICKS_PER_SYMBOL = 50
_AT = datetime(2026, 10, 17, 9, tzinfo=UTC)


@pytest.fixture
def report(request: pytest.FixtureRequest) -> Callable[[str], None]:
    """Writes a measured figure on the test run's own terminal, `-s` or not."""
    reporter = request.config.pluginmanager.get_plugin("terminalreporter")

    def write(line: str) -> None:
        if reporter is not None:
            reporter.write_line(line)

    return write


@pytest.fixture
def gate_never_closes(
    weight_gate_lifted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lifts the 70 % line (`weight_gate_lifted`) and the venue's cap, so a measurement is not cut
    off where the gate would close or the venue would refuse the next bot: what N bots *would*
    spend."""
    monkeypatch.setattr(other_active_bot, "MAX_ACTIVE_BOTS_PER_VENUE", 1_000)


def _tick(app: BootedTwoVenues, symbol: str, price: float) -> None:
    """What the venue's kline websocket publishes for a trade of `symbol` at `price`."""
    app.engine.event_bus.emit(
        MarketTickEvent(
            MarketData(
                symbol=symbol,
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
            market_type=MarketType.FUTURES_USD_M,
            market_data_venue=FUTURES.market_data_venue,
        )
    )


@pytest.mark.parametrize("count", COUNTS)
def test_measured_tick_fan_out_to_n_bots_reaches_only_the_bot_of_the_symbol(
    both_venues: FakeExchange,
    gate_never_closes: None,
    count: int,
    report: Callable[[str], None],
) -> None:
    with booted_two_venues(both_venues) as app:
        symbols = FUTURES_SYMBOLS[:count]
        bots = run_bots(app, FUTURES, symbols)
        executors = app.engine.container.resolve(BotExecutors)
        received = {
            symbol: _count_ticks(executors.get(bot_id))
            for symbol, bot_id in bots.items()
        }

        started = time.perf_counter()
        for _ in range(TICKS_PER_SYMBOL):
            for symbol in symbols:
                _tick(app, symbol, 64_000.0)
        elapsed = time.perf_counter() - started

        ticks = TICKS_PER_SYMBOL * count
        report(
            f"MEASURED fan-out N={count}: {ticks} ticks in {elapsed * 1000:.1f} ms = "
            f"{elapsed / ticks * 1_000_000:.0f} us per tick"
        )
        for symbol in symbols:
            assert received[symbol].count == TICKS_PER_SYMBOL, (
                f"{symbol}'s bot heard {received[symbol].count} ticks, not only its own"
            )


class _Heard:
    """Counts the ticks one executor is handed, by wrapping the real `facts.on_tick`."""

    def __init__(self) -> None:
        self.count = 0


def _count_ticks(executor: object) -> _Heard:
    heard = _Heard()
    facts = executor.facts  # type: ignore[attr-defined]
    real = facts.on_tick

    def counting(tick: object) -> None:
        heard.count += 1
        real(tick)

    facts.on_tick = counting
    return heard


@pytest.mark.parametrize("count", COUNTS)
def test_measured_request_weight_of_starting_n_bots_on_one_venue(
    both_venues: FakeExchange,
    gate_never_closes: None,
    count: int,
    report: Callable[[str], None],
) -> None:
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        mark = meter.mark()
        run_bots(app, FUTURES, FUTURES_SYMBOLS[:count])
        spent = meter.weight_since(mark)
        by_path = dict(meter.by_path_since(mark).most_common(4))

    per_bot = spent / count
    report(
        f"MEASURED start weight N={count}: {spent} total, {per_bot:.0f} per bot "
        f"({spent / GATE_LINE:.0%} of the gate's {GATE_LINE}); top {by_path}"
    )
    assert spent > 0


def _an_idle_minute(app: BootedTwoVenues, symbols: tuple[str, ...]) -> None:
    """A minute with no fill: the price watch's beat every `CHECK_EVERY_SECONDS` of the clock the
    bots measure by, and a tick a second on every symbol."""
    for second in range(60):
        if second % int(CHECK_EVERY_SECONDS) == 0:
            app.monotonic.advance(CHECK_EVERY_SECONDS)
            app.ticker.fire()
        for symbol in symbols:
            _tick(app, symbol, 64_000.0)


@pytest.mark.parametrize("count", COUNTS)
def test_measured_request_weight_of_n_idle_bots_for_a_minute(
    both_venues: FakeExchange,
    gate_never_closes: None,
    count: int,
    report: Callable[[str], None],
) -> None:
    """A minute with no fill: the price watch's beat every `CHECK_EVERY_SECONDS` of the clock the
    bots measure by, and a tick a second on every symbol."""
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        symbols = FUTURES_SYMBOLS[:count]
        run_bots(app, FUTURES, symbols)
        mark = meter.mark()

        _an_idle_minute(app, symbols)
        spent = meter.weight_since(mark)
        by_path = dict(meter.by_path_since(mark).most_common(4))

    report(
        f"MEASURED idle minute N={count}: {spent} weight = {spent / count:.0f} per bot "
        f"({spent / GATE_LINE:.0%} of the gate's {GATE_LINE}); top {by_path}"
    )
    per_bot = spent / count
    assert per_bot <= IDLE_WEIGHT_PER_BOT_BUDGET, (
        f"an idle bot spends {per_bot:.0f} a minute, past the {IDLE_WEIGHT_PER_BOT_BUDGET} the "
        "cap was sized with"
    )


#: `positionRisk` without a symbol is one request for the whole account (Binance weight 5).
POSITION_RISK_PATH = "GET /fapi/v3/positionRisk"
POSITION_RISK_WEIGHT = 5
BEATS_PER_MINUTE = int(60 / CHECK_EVERY_SECONDS)


@pytest.mark.parametrize("count", COUNTS)
def test_n_idle_bots_read_the_accounts_positions_once_a_beat_between_them(
    both_venues: FakeExchange,
    gate_never_closes: None,
    count: int,
    report: Callable[[str], None],
) -> None:
    """`BOT-184`: the bots of a venue are on one account, and `positionRisk` is one request for all
    of it, so a beat reads it once for the whole sweep, not once per bot and watch (it was two a
    beat per bot: 120 weight a minute for one bot, 2,405 for twenty)."""
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        symbols = FUTURES_SYMBOLS[:count]
        run_bots(app, FUTURES, symbols)
        mark = meter.mark()

        _an_idle_minute(app, symbols)
        spent = meter.by_path_since(mark)[POSITION_RISK_PATH]

    # One read a beat, and one more when a bot's own order dropped the shared reading in mid-beat
    # (twenty bots do: the first beat's order drops it once).
    allowed = POSITION_RISK_WEIGHT * (BEATS_PER_MINUTE + 1)
    report(
        f"MEASURED positionRisk, idle minute N={count}: {spent} weight "
        f"(one read a beat is {POSITION_RISK_WEIGHT * BEATS_PER_MINUTE}, allowed {allowed})"
    )
    assert spent <= allowed, (
        f"{count} idle bots spent {spent} weight a minute reading the account's positions: "
        "more than one read a beat between them"
    )


@pytest.mark.parametrize("count", (1, 5))
def test_measured_request_weight_of_one_fill_does_not_grow_with_the_bots_beside_it(
    both_venues: FakeExchange,
    gate_never_closes: None,
    count: int,
    report: Callable[[str], None],
) -> None:
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        symbols = FUTURES_SYMBOLS[:count]
        run_bots(app, FUTURES, symbols)
        mark = meter.mark()

        app.move_price(
            FUTURES, 62_900, symbols[-1]
        )  # the 63,000 buy of the last bot fills
        spent = meter.weight_since(mark)

    report(f"MEASURED one fill beside N={count} bots: {spent} weight")
    assert spent <= 25, "a fill costs what it costs alone (PER_FILL_BUDGET of BUG-216)"


@pytest.mark.parametrize("count", COUNTS)
def test_measured_request_weight_of_n_bots_reconciling_together_after_a_restart(
    both_venues: FakeExchange,
    gate_never_closes: None,
    count: int,
    report: Callable[[str], None],
) -> None:
    """The minute after the app restarts with N bots running: the venue's session opens once and
    every RECOVERING bot of the venue reconciles (`TradingSwitchChangedEvent`)."""
    symbols = FUTURES_SYMBOLS[:count]
    with booted_two_venues(both_venues) as first:
        bots = run_bots(first, FUTURES, symbols)

    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as second:
        for bot_id in bots.values():
            assert second.bot(bot_id).state is S.RECOVERING
        mark = meter.mark()

        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=FUTURES)
        )
        spent = meter.weight_since(mark)
        by_path = dict(meter.by_path_since(mark).most_common(4))
        running = sum(second.bot(i).state is S.RUNNING for i in bots.values())

    report(
        f"MEASURED restart N={count}: {running} of {count} RUNNING again, {spent} weight = "
        f"{spent / count:.0f} per bot ({spent / GATE_LINE:.0%} of the gate's {GATE_LINE}); "
        f"top {by_path}"
    )
    assert running == count


def test_a_full_venue_of_idle_bots_leaves_the_gate_the_room_its_starts_and_fills_need(
    both_venues: FakeExchange, gate_never_closes: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cap's justification as a test: at `MAX_ACTIVE_BOTS_PER_VENUE` idle bots the minute's
    weight stays under three fifths of the gate's line, so the other two fifths (about 670) take
    a start (about 300) and a burst of fills (19 each) without the gate closing."""
    monkeypatch.setattr(
        other_active_bot, "MAX_ACTIVE_BOTS_PER_VENUE", MAX_ACTIVE_BOTS_PER_VENUE
    )
    meter = both_venues.urls.weights
    with booted_two_venues(both_venues) as app:
        symbols = FUTURES_SYMBOLS[:MAX_ACTIVE_BOTS_PER_VENUE]
        run_bots(app, FUTURES, symbols)
        mark = meter.mark()
        _an_idle_minute(app, symbols)
        spent = meter.weight_since(mark)

    assert spent <= GATE_LINE * 0.6, (
        f"{MAX_ACTIVE_BOTS_PER_VENUE} idle bots spend {spent} of the gate's {GATE_LINE} a "
        "minute: the cap leaves the gate too little room"
    )


def test_a_burst_of_starts_stops_at_the_gate_before_the_exchange_limit(
    both_venues: FakeExchange,
    monkeypatch: pytest.MonkeyPatch,
    report: Callable[[str], None],
) -> None:
    """The real gate, not lifted: eight starts inside a minute (the cap lifted so the count is not
    what refuses them). The start lock runs them one at a time, the gate closes at 70 %, and the
    starts it refuses say the exchange asked for a pause; the minute's weight never reaches the
    exchange's own limit, which is what a ban would need."""
    monkeypatch.setattr(other_active_bot, "MAX_ACTIVE_BOTS_PER_VENUE", 1_000)
    meter = both_venues.urls.weights
    # The eight starts are "inside a minute" by construction, not by the wall clock's luck: on a
    # slow runner they used to cross a calendar minute, which reset the weight (`BUG-232`).
    meter.use_clock(lambda: 0.0)
    with booted_two_venues(both_venues) as app:
        mark = meter.mark()
        accepted = 0
        refused: list[str] = []
        for symbol in FUTURES_SYMBOLS[:8]:
            started = start_bot(app, create_bot(app, FUTURES, symbol))
            if started.accepted:
                accepted += 1
            else:
                refused.append(started.message)
        spent = meter.weight_since(mark)

    report(
        f"MEASURED burst of 8 starts: {accepted} accepted, {len(refused)} refused by the gate, "
        f"{spent} weight of the exchange's {FUTURES_WEIGHT}"
    )
    assert 4 <= accepted < 8, (
        "the gate lets about five starts through and refuses the rest"
    )
    assert all("asked for a pause" in message for message in refused), refused
    assert spent < FUTURES_WEIGHT
