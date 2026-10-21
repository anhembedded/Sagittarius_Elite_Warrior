"""`EPIC-044B` - a Grid started away from its range waits, on the composed app over the fake exchange.

The owner's rule of 2026-10-21 (ADR 044 D1): the bot starts, places nothing and holds nothing, and
lays its ladder when the price is inside the range. Here the real Start use case runs against the
fake Binance server with the market 55,000 above `GRID`'s range (48,000-52,000, take profit
60,000): nothing rests on the exchange; a tick through the range and the book at 50,000 lay the
ladder; a restart in between returns the bot to waiting after its reconcile, with nothing laid.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

from .grid_fake_exchange import SYMBOL, FakeExchange, booted, resting
from .test_a_bot_owns_its_price_stream_on_the_fake_exchange import (
    _INSIDE_THE_RANGE,
    _publish_tick,
    _started,
)

S = BotLifecycleState
_ABOVE_THE_RANGE = 55_000


class _Lines(logging.Handler):
    """What the bot's logger said, kept: the `App.*` loggers do not propagate to `caplog`."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


def test_a_bot_started_above_its_range_places_nothing_until_the_price_enters_it(
    exchange: FakeExchange,
) -> None:
    exchange.urls.spot_account.set_last_price(SYMBOL, Decimal(_ABOVE_THE_RANGE))
    lines = _Lines()
    logger = logging.getLogger("App.Bots.GridExecutor")
    logger.addHandler(lines)
    try:
        with booted(exchange) as app:
            bot_id = _started(app)

            assert app.bot(bot_id).state is S.AWAITING_RANGE
            assert resting(app.urls) == {}, "nothing rests on the exchange"

            _publish_tick(app, float(_ABOVE_THE_RANGE))
            assert app.bot(bot_id).state is S.AWAITING_RANGE

            app.move_price(int(_INSIDE_THE_RANGE))
            _publish_tick(app, _INSIDE_THE_RANGE)
            app.deliver()

            assert app.bot(bot_id).state is S.RUNNING
            assert resting(app.urls), "the ladder rests once the price is inside"
    finally:
        logger.removeHandler(lines)
    tagged = [line for line in lines.lines if "[range-" in line]
    assert any("waiting for the price to enter it [range-wait]" in x for x in tagged)
    assert any(
        "entered the range 48000-52000" in x and "[range-entry]" in x for x in tagged
    )


def test_a_restart_while_waiting_lays_nothing_and_the_reconcile_returns_the_bot_to_waiting(
    exchange: FakeExchange,
) -> None:
    exchange.urls.spot_account.set_last_price(SYMBOL, Decimal(_ABOVE_THE_RANGE))
    with booted(exchange) as first:
        bot_id = _started(first)
        assert first.bot(bot_id).state is S.AWAITING_RANGE

    with booted(exchange) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        assert second.bot(bot_id).lifecycle.recovering_from is S.AWAITING_RANGE
        assert resting(second.urls) == {}
