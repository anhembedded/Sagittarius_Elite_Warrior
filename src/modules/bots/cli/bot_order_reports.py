"""`BOT-187` — `bot order <id>` as a `Report`: the orders a bot's own file records.

The orders are the ones the Bots tab's "orders" table shows (`BotProgress.orders`), read from
the bot's saved runtime and never from the exchange, so the report says so in its first line
and in its payload (`source: "stored"`). The payload's keys are the contract with scripts
(`test_the_bot_order_payload_keys_are_pinned`): a field is added within a version, never renamed.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    JsonValue,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    AT_REST_STATES,
    UnreadableBotEntry,
)

ORDER_COMMAND = "bot-order"
SCHEMA_VERSION = 1

#: The one value `source` takes today; live open orders are a later source (`BOT-187` follow-up).
STORED_SOURCE = "stored"

STORED_NOTE = "Orders as the bot's file records them, not read from the exchange."
ORDERS_UNKNOWN = (
    "Orders unknown: the bot is not at rest but its file holds no readable run record."
)
NO_HOST_NOTE = (
    "No copy of the app is running: the file may be behind the exchange "
    "(a bot shown as RUNNING is running nowhere)."
)


def bot_order_report(snapshot: BotSnapshot, *, app_running: bool) -> Report:
    """The orders of one readable bot.

    A bot that is not at rest and has no run record has an unreadable runtime (the reader
    logged why): "no orders" would be a claim the file does not support, so it says unknown."""
    orders = snapshot.progress.orders if snapshot.progress is not None else ()
    known = snapshot.progress is not None or snapshot.state.value in AT_REST_STATES
    payload: dict[str, JsonValue] = {
        "source": STORED_SOURCE,
        "app_running": app_running,
        "bot_id": snapshot.bot_id,
        "name": snapshot.name,
        "symbol": snapshot.symbol,
        "state": snapshot.state.value,
        "orders_known": known,
        "orders": [_order_payload(order) for order in orders],
        "unreadable": None,
    }
    return Report(
        ORDER_COMMAND,
        SCHEMA_VERSION,
        payload,
        _layout(snapshot.bot_id, orders, known, app_running),
    )


def unreadable_order_report(bot: UnreadableBotEntry, *, app_running: bool) -> Report:
    """A bot whose file this build refused: named with its path, never an empty list."""
    payload: dict[str, JsonValue] = {
        "source": STORED_SOURCE,
        "app_running": app_running,
        "bot_id": bot.bot_id,
        "name": None,
        "symbol": None,
        "state": bot.state,
        "orders_known": False,
        "orders": [],
        "unreadable": {"path": bot.path, "reason": bot.reason},
    }
    layout = (
        ReportSection(
            f"Bot {bot.bot_id}",
            (
                _field("State", bot.state),
                _field("File", bot.path),
                _field("Why", bot.reason),
                _field("Orders", "unknown: the bot's file cannot be read"),
            ),
        ),
    )
    return Report(ORDER_COMMAND, SCHEMA_VERSION, payload, layout)


def _order_payload(order: BotOrderLine) -> dict[str, JsonValue]:
    return {
        "level": order.level,
        "side": order.side,
        "price": str(order.price),
        "quantity": str(order.quantity),
        "executed": str(order.executed),
        "state": order.state,
        "client_order_id": order.client_order_id,
    }


def _layout(
    bot_id: str, orders: tuple[BotOrderLine, ...], known: bool, app_running: bool
) -> tuple[ReportSection, ...]:
    notes = [ReportRow.of(STORED_NOTE)]
    if not app_running:
        notes.append(ReportRow.of(NO_HOST_NOTE))
    body = (
        [ReportRow.of(ORDERS_UNKNOWN if not known else "No orders.")]
        if not orders
        else [
            _row(
                "LEVEL",
                "SIDE",
                "PRICE",
                "QUANTITY",
                "EXECUTED",
                "STATE",
                "CLIENT ORDER ID",
            ),
            *(_order_row(order) for order in orders),
        ]
    )
    return (
        ReportSection(None, tuple(notes)),
        ReportSection(f"Orders of bot {bot_id}", tuple(body)),
    )


def _field(label: str, value: str) -> ReportRow:
    return ReportRow((ReportCell(label, 12), ReportCell(value)))


def _row(
    level: str,
    side: str,
    price: str,
    quantity: str,
    executed: str,
    state: str,
    client_order_id: str,
) -> ReportRow:
    return ReportRow(
        (
            ReportCell(level, 7),
            ReportCell(side, 6),
            ReportCell(price, 14),
            ReportCell(quantity, 14),
            ReportCell(executed, 14),
            ReportCell(state, 9),
            ReportCell(client_order_id),
        )
    )


def _order_row(order: BotOrderLine) -> ReportRow:
    return _row(
        str(order.level),
        order.side,
        str(order.price),
        str(order.quantity),
        str(order.executed),
        order.state or "-",
        order.client_order_id,
    )
