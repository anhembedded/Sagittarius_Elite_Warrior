# EPIC-009D — D6 continued: fake Binance WebSocket server

**Status:** 🔴 Not started
**Depends on:** `EPIC-009C` (extends the same fake-server module)

## What

`EPIC-009C` covered REST only. `AsyncClient.create()` /
`bsm.kline_socket()` / `bsm.multiplex_socket()` — the websocket path used
by `BinanceWebsocketService` (the live-stream adapter) — are still
mocked at their two entry points (`AsyncClient`, `BinanceSocketManager`
patched in `conftest.py`), not run against a real fake server.

Extend `binance_fake_server.py` (or a sibling module) to also speak
enough of Binance's websocket protocol to let the real
`BinanceSocketManager`/`AsyncClient` connect and receive a scripted
sequence of kline messages, so the live-stream path can eventually be
proven the same way REST now is — no hand-written substitute for the
websocket entry points.

## Why this is separate from `EPIC-009C`

A real websocket protocol (framing, the specific message shapes
`_parse_kline` expects) is materially more work than a REST GET handler.
Scoped as its own piece rather than blocking `EPIC-009C`'s (much cheaper,
already-delivered) value.

## Open questions before starting

- Does closing this actually unblock anything currently blocked, or is
  the REST-only fake server already sufficient for every Sanity-tier use
  case? (Likely yes — the 3 use cases `BUG-045` named were all REST-only.
  This piece's value may be for `Integration`/Desktop E2E instead, per
  the ADR's D2b scope note that this transport should serve the whole
  pyramid, not just Sanity.)
- Confirm before starting whether this belongs to this epic at all, or
  should be its own epic once Sanity's own scope is fully closed.
