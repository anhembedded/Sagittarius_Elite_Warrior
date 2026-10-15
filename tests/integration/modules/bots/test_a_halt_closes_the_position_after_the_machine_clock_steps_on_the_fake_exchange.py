"""`BUG-221` — a halt closes the position even when the machine clock stepped under the session.

@details The owner's Futures Testnet bot (2026-10-15): every signed request answered `-1021` for
ten minutes after the clock stepped, the halt's cancel and its close included, and the long
stayed open until the session's clock reading expired. The composed app over the Futures fake
exchange, which applies Binance's timestamp rule: the clock steps after the bot is running, the
feed goes silent, and the halt that follows must still end flat.
"""

from __future__ import annotations

from fake_exchange.history_log import exchange_clock_skewed_by
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
)

from .futures_bots_world import OPENING_QUANTITY, ORDER_QUANTITY, booted_futures_bots
from .grid_fake_exchange import FakeExchange
from .test_a_futures_grid_halts_and_recovers_on_the_fake_exchange import (
    _publish_tick,
    _started,
)

#: The machine's clock is 3 s ahead of the exchange's after the step.
_STEP_MS = -3000


def test_a_halt_after_a_clock_step_still_cancels_and_closes(
    futures: FakeExchange,
) -> None:
    with booted_futures_bots(futures) as app:
        bot_id = _started(app)
        app.move_price(62900)
        assert app.position() == OPENING_QUANTITY + ORDER_QUANTITY
        _publish_tick(app, 63000.0)
        futures.urls.clock.enforcing = True

        with exchange_clock_skewed_by(_STEP_MS):
            app.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
            app.ticker.fire()
            app.deliver()

            assert futures.urls.clock.rejected >= 1, "the step was felt by the session"

        assert app.runtime(bot_id).reason is GridReason.PRICE_FEED_STALE
        assert app.bot(bot_id).state is BotLifecycleState.STOPPED
        assert app.position() == 0, "the close was not the call that failed"
        assert app.resting() == {}
