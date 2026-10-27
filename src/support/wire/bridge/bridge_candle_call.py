"""`EPIC-047H` — the bridge's `candles` call: a window of the host's closed candles, read-only.

@details `{"type":"call","id":n,"method":"candles","params":{"venue","symbol","timeframe","limit","before"?}}` is
answered by `{"window": <sew.candle-window/1>}`. The host's store is read through `IBridgeCandles` (plain
`sqlite3`, `mode=ro`); a build with none answers `no_candles`, and a query this build cannot name answers
`bad_candles` with the words, never a path or an exception's text. The call is a read of a local file, so it
runs on the session's thread like `snapshot`.
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    MESSAGE_LIMIT,
    CallError,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    CandleQuery,
    IBridgeCandles,
    UnknownCandleSeriesError,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

_BEFORE_WORDS = "before is an ISO moment with a time zone"


def serve_candles(
    candles: IBridgeCandles | None, roots: WireRoots, params: dict[str, object]
) -> dict[str, object]:
    if candles is None:
        raise CallError("no_candles", "this host serves no candles")
    try:
        window = candles.window(_query_of(params))
    except UnknownCandleSeriesError as failure:
        raise CallError("bad_candles", str(failure)[:MESSAGE_LIMIT]) from failure
    return {"window": roots.encode(window.root, window.value)}


def _query_of(params: dict[str, object]) -> CandleQuery:
    venue, symbol, timeframe = (params.get(k) for k in ("venue", "symbol", "timeframe"))
    limit, before = params.get("limit"), params.get("before")
    if (
        not all(type(v) is str for v in (venue, symbol, timeframe))
        or type(limit) is not int
    ):
        raise CallError(
            "bad_candles",
            "a candles call names a venue, a symbol, a timeframe and a limit",
        )
    return CandleQuery(
        venue=str(venue),
        symbol=str(symbol),
        timeframe=str(timeframe),
        limit=limit,
        before=None if before is None else _moment(before),
    )


def _moment(raw: object) -> datetime:
    if type(raw) is not str:
        raise CallError("bad_candles", "before is an ISO moment with a time zone")
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError as failure:
        raise CallError(
            "bad_candles", "before is an ISO moment with a time zone"
        ) from failure
    if moment.tzinfo is None:
        raise CallError("bad_candles", "before is an ISO moment with a time zone")
    return moment
