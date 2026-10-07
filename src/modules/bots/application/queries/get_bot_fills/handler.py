"""`EPIC-029F` — handler for `GetBotFillsQuery`.

Read from the venue's order history, not from the bot's runtime: the runtime
keeps what rests now, and an order that filled has moved on. Every order a
bot sends carries its id as the client order tag (ADR D5), so the history is
filtered by `tag_of`, the rule trading itself attributes orders by. The read
starts at the run's start, or at the bot's creation before any run.

A read the venue refuses for a reason the Connect step also names (`BUG-181`) is
answered as `BotFills.refused`, not raised: it is one cause, told once.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills.query import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills.result import (
    BotFill,
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HISTORY_PAGE_SIZE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_request import (
    HistoryRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

#: Pages of 50 orders one read scans: a bot's own orders are a share of the
#: symbol's history, and a screen read must stay a few requests long.
MAX_PAGES = 4
#: What a refused read says it was reading, for the Connect failure's detail.
_THE_FILLS = "the bot's fills"


class GetBotFillsQueryHandler(IQueryHandler[GetBotFillsQuery, BotFills]):
    def __init__(self, store: IBotStore, ports: IVenueTradingPorts) -> None:
        self._store = store
        self._ports = ports

    def execute(self, query: GetBotFillsQuery) -> BotFills:
        try:
            bot = self._store.load(BotId(query.bot_id)).bot
        except BotNotFoundError:
            return BotFills(problem=f"bot {query.bot_id} no longer exists")
        venue = bot.definition.venue
        if venue not in self._ports.enabled():
            return BotFills(problem=f"{venue.value} is not enabled")
        since = bot.lifecycle.run_started_at or bot.created_at
        activity = self._ports.get(venue).account_activity
        fills: list[BotFill] = []
        for page in range(MAX_PAGES):
            try:
                rows = activity.order_history(
                    HistoryRequest(bot.definition.symbol, since, page)
                )
            except AccountHistoryUnavailableError as unavailable:
                if unavailable.kind is None:
                    raise
                return BotFills(
                    refused=ConnectFailure(
                        AccountSource.for_venue(venue), unavailable.kind, _THE_FILLS
                    )
                )
            fills.extend(
                _fill(record)
                for record in rows.rows
                if _is_fill_of(record, query.bot_id)
            )
            if not rows.rows or (page + 1) * HISTORY_PAGE_SIZE >= rows.total_rows:
                return BotFills(tuple(fills))
        return BotFills(tuple(fills), truncated=True)


def _is_fill_of(record: OrderRecord, bot_id: str) -> bool:
    return (
        record.executed_quantity > 0
        and tag_of(str(record.order.client_order_id)) == bot_id
    )


def _fill(record: OrderRecord) -> BotFill:
    order = record.order
    return BotFill(
        time=order.order_time or record.created_at,
        side=order.side.value,
        price=record.average_price,
        quantity=record.executed_quantity,
        client_order_id=str(order.client_order_id),
    )
