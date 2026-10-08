"""`EPIC-035F` — a key revoked mid-run is named, on the composed app and the fake exchange.

`create_app()` builds trading (the real execute handler and connection check) and
bots (executors, the price watch); only the network is the fake server, whose key
policy answers `-2015` for a refused key exactly as Binance does for a revoked
one. What each journey proves is the whole path: the exchange's `-2015` → the
connection check's `KEY_REJECTED` → the order gate → the bot's reason, and the
halt that does not try a cancel it cannot make.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_key_probe import (
    KEY_PROBE_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

from .grid_fake_exchange import (
    BootedApp,
    FakeExchange,
    booted,
    resting,
)
from .test_a_bot_owns_its_price_stream_on_the_fake_exchange import (
    _INSIDE_THE_RANGE,
    _publish_tick,
    _started,
)

S = BotLifecycleState
_KEY = "fake-key"


def _revoke(exchange: FakeExchange) -> int:
    """The exchange stops accepting the key; returns how many requests it has seen."""
    exchange.urls.keys.known = {_KEY}
    exchange.urls.keys.refused = {_KEY}
    return len(exchange.urls.requests)


def _cancels_since(exchange: FakeExchange, seen: int) -> list[tuple[str, str]]:
    return [r for r in exchange.urls.requests[seen:] if r[0] == "DELETE"]


def _halted_by_the_key(app: BootedApp, bot_id: str) -> None:
    assert app.bot(bot_id).state is S.HALTED
    runtime = app.runtime(bot_id)
    assert runtime.reason is GridReason.KEY_REJECTED, runtime.reason
    assert "may still rest" in runtime.reason_detail


def test_the_next_order_after_a_revocation_halts_with_key_rejected_not_switch_off(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        seen = _revoke(exchange)

        app.move_price(48700)  # the 48,800 buy fills; its counter order is refused

        _halted_by_the_key(app, bot_id)
        assert _cancels_since(exchange, seen) == [], "no cancel can work; none tried"
        assert resting(app.urls), "what rests, rests: the bot says so"


def test_a_revocation_is_found_between_orders_by_the_probe(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        bot_id = _started(app)
        _publish_tick(app, _INSIDE_THE_RANGE)
        orders = resting(app.urls)
        seen = _revoke(exchange)

        beat = KEY_PROBE_EVERY_SECONDS / 2
        for _ in range(2):  # the feed stays alive; only the key is gone
            app.monotonic.advance(beat)
            _publish_tick(app, _INSIDE_THE_RANGE)
            app.ticker.fire()

        _halted_by_the_key(app, bot_id)
        assert _cancels_since(exchange, seen) == []
        assert resting(app.urls) == orders, "nothing was cancelled or placed"
