"""`BUG-189` — a machine whose clock is not the exchange's, in the composed app.

`run_started_at`, the history windows and the checkpoint's read-from are
stamped on the machine's clock; the exchange stamps its orders and fills on its
own. A machine a minute fast (the owner's, `BUG-111`) opened every history
window after the bot's own opening buy and ladder, so the derivation counted
nothing and the periodic reconcile halted a healthy bot on `inventory_mismatch`.
A machine behind the exchange closed every window before the newest fills.

The fake exchange's clock is skewed from the machine's; everything else is the
journey of `test_a_user_stream_gap_on_the_fake_exchange`: Start, the opening
buy, the ladder, then the stream's catch-up reconcile.
"""

from __future__ import annotations

import pytest
from fake_exchange.history_log import exchange_clock_skewed_by
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamState,
)

from .grid_fake_exchange import FakeExchange, booted
from .test_a_user_stream_gap_on_the_fake_exchange import _stream_says
from .test_grid_bot_against_fake_server import _started

S = BotLifecycleState

#: The exchange's clock against the machine's, in ms: the machine 90 s fast (a
#: minute past the checkpoint's overlap), and 20 s slow.
FAST_MACHINE = -90_000
SLOW_MACHINE = 20_000


@pytest.mark.parametrize("skew_ms", [FAST_MACHINE, SLOW_MACHINE])
def test_a_reconcile_does_not_halt_a_healthy_bot_whose_machine_clock_is_off(
    exchange: FakeExchange, skew_ms: int
) -> None:
    with exchange_clock_skewed_by(skew_ms), booted(exchange) as app:
        bot_id = _started(app)
        held = app.runtime(bot_id).inventory
        assert app.bot(bot_id).state is S.RUNNING
        assert held > 0, "the opening buy filled"

        _stream_says(app, UserStreamState.CONNECTED)
        _stream_says(app, UserStreamState.CONNECTED)

        assert app.bot(bot_id).state is S.RUNNING, app.runtime(bot_id).reason_detail
        assert app.runtime(bot_id).inventory == held
