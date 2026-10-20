"""`BOT-197` - a person's manual order that opens the order session resumes no RECOVERING bot.

@details After a restart the venue's session is closed and a bot is RECOVERING. A manual order on
the desk opens the session itself (`EPIC-034C`), and the opening used to reconcile every
RECOVERING bot of the venue, so a real-money bot the owner did not resume laid its ladder. The
opening is now announced as a person's (ADR 038 O2: only the bot's own Resume or the host's
`--resume-recovering` resumes it). Composed app on the fake exchange, from a real restart.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

from .crowd_bots_world import run_bots
from .grid_fake_exchange import FakeExchange, ladder
from .two_venues_bots_world import SPOT, SYMBOL, booted_two_venues

S = BotLifecycleState


def test_a_manual_order_that_opens_the_session_leaves_a_recovering_bot_waiting_for_its_own_resume(
    both_venues: FakeExchange,
) -> None:
    with booted_two_venues(both_venues) as first:
        waiting = run_bots(first, SPOT, (SYMBOL,))[SYMBOL]

    with booted_two_venues(both_venues, open_sessions=False) as second:
        assert second.bot(waiting).state is S.RECOVERING
        assert second.scopes[SPOT].session_state.enabled is False

        order = second.engine.dispatch(
            ExecuteOrderCommand,
            ExecuteOrderCommand(
                order_request=PreviewOrderQuery(
                    venue=SPOT,
                    symbol="ETHUSDT",
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=Decimal("0.01"),
                    reference_price=Decimal(3000),
                ),
                live=True,
                opens_session=True,
            ),
        )
        second.deliver()

        assert order.blocked_by is None, order.blocked_by
        assert second.scopes[SPOT].session_state.enabled is True, "the order opened it"
        assert second.bot(waiting).state is S.RECOVERING, "a manual order woke the bot"

        own = second.engine.dispatch(
            ResumeBotCommand, ResumeBotCommand(waiting, real_money_confirmed=True)
        )
        assert isinstance(own, BotCommandResult)
        assert own.accepted, own.message
        assert second.bot(waiting).state is S.RUNNING
        assert ladder(second.runtime(waiting)) != set()
