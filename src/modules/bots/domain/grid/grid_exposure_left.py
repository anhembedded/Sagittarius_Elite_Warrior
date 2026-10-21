"""`EPIC-045B` - what a stopped Grid's record says it still holds (`IBotKind.exposure_left`).

Read from the stored runtime as plain JSON, because the domain does not import the application's
codec (`grid_runtime_codec`). It reads the four places a Grid keeps a claim on the account: the base
it holds (`inventory`, and `earlier_runs_base` a start read from the exchange), an order at a
level, an order a pause held, and a protective stop that is not over. A field it cannot read is a
reason to keep the bot, not to forget it: the record is the only thing it has to go on.

@par Dust (`EPIC-045` D4a)
A stop that sold the coin still leaves the remainder the venue will not take (`exit_dust.py`: a base
worth less than the venue's minimum order), so a bot that sold everything it could still holds a
sliver, and refusing on any nonzero base would make no Grid deletable. The exchange's minimum
is not in the record, so the base is valued at the highest price the record holds (the last
`mark_price`, the run's `start_price`, or a level's price: the highest is the cautious one) and a
value under `DUST_QUOTE_VALUE` quote units is let go. A base with no price to value it by is never let go.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import JsonValue

#: A base worth less than this, in the quote asset, is let go: no Spot venue the bot trades on
#: accepts an order this small, so the stop could not have sold it. At most this much is orphaned.
DUST_QUOTE_VALUE = Decimal(10)
_OVER = frozenset({"absent", "ended"})
_UNREADABLE = "its record cannot be read, so what it holds is not known"


def grid_exposure_left(runtime: Mapping[str, JsonValue]) -> str | None:
    """A sentence naming what the record holds, or `None` when it holds nothing."""
    if not runtime:
        return None
    try:
        return (
            _base_held(runtime)
            or _live_orders(runtime)
            or _owed_orders(runtime)
            or _protective_stops(runtime)
        )
    except (InvalidOperation, TypeError, ValueError):
        return _UNREADABLE


def _base_held(runtime: Mapping[str, JsonValue]) -> str | None:
    held = _decimal(runtime, "inventory") + _decimal(runtime, "earlier_runs_base")
    if held == 0:
        return None
    price = _highest_price(runtime)
    if price is not None and abs(held) * price < DUST_QUOTE_VALUE:
        return None
    return (
        f"its record holds {held} of the base asset (inventory and earlier runs); "
        "sell it first (`bot start`, then `bot stop --close-position`)"
    )


def _highest_price(runtime: Mapping[str, JsonValue]) -> Decimal | None:
    levels = runtime.get("levels", [])
    if not isinstance(levels, list):
        raise TypeError("levels")
    prices = [runtime.get("mark_price"), runtime.get("start_price")] + [
        level.get("price") for level in levels if isinstance(level, dict)
    ]
    known = [Decimal(str(price)) for price in prices if price is not None]
    return max(known) if known else None


def _decimal(runtime: Mapping[str, JsonValue], field: str) -> Decimal:
    value = runtime.get(field)
    return Decimal(0) if value is None else Decimal(str(value))


def _live_orders(runtime: Mapping[str, JsonValue]) -> str | None:
    levels = runtime.get("levels", [])
    if not isinstance(levels, list):
        raise TypeError("levels")
    live = sum(1 for level in levels if isinstance(level, dict) and level.get("order"))
    return f"its record shows {live} order(s) resting at its levels" if live else None


def _owed_orders(runtime: Mapping[str, JsonValue]) -> str | None:
    held = runtime.get("held", [])
    if not isinstance(held, list):
        raise TypeError("held")
    return f"its record shows {len(held)} order(s) it owes a level" if held else None


def _protective_stops(runtime: Mapping[str, JsonValue]) -> str | None:
    stops = runtime.get("protective_stops", [])
    if not isinstance(stops, list):
        raise TypeError("protective_stops")
    open_ = sum(
        1
        for stop in stops
        if not isinstance(stop, dict) or stop.get("state") not in _OVER
    )
    return f"its record shows {open_} protective stop(s) not over" if open_ else None
