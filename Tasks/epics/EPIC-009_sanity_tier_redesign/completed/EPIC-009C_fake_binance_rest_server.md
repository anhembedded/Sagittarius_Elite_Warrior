# EPIC-009C — D6: fake Binance REST server, closing BUG-045

**Status:** ✅ Done — 2026-08-25 (REST only; websocket is `EPIC-009D`)
**Depends on:** `EPIC-009A` (`booted_app` is where it's wired in)

## What

`tests/sanity/binance_fake_server.py` — a stdlib-only
`http.server.HTTPServer` on a background thread, serving exactly the
three REST paths this application calls (verified against
`src/infrastructure/binance/client.py`'s real call sites, not assumed):
`GET /api/v3/ping`, `/api/v3/exchangeInfo`, `/api/v3/klines`.

`conftest.py`'s `booted_app` points `binance.client.Client.API_URL` (a
class attribute on the third-party class) at the fake server's URL for
the fixture's scope, restored after. The real `Client` — its kline
mapping, pagination, HTTP behavior — runs completely unmodified; only the
endpoint moves. Explicitly not a hand-written substitute for
`IExchangeClient`, which was rejected as the shape that produced
`BUG-026`/`BUG-027`.

## Why REST only, for now

`PythonBinanceClient` (the adapter three previously-blocked use cases
depend on) only calls REST. `AsyncClient`/`BinanceSocketManager` (the
websocket path, used by the live-stream adapter) stay mocked at their two
entry points, same as before this piece — a real websocket protocol is
materially more work than a REST GET handler, and out of scope here.

## Proof

`tests/sanity/test_composition_root.py::test_every_use_case_resolves_to_a_handler`
— all 17 use cases resolve, `_BLOCKED_BY_BUG` deleted (was 3 entries, all
`BUG-045`). Full gate re-run clean: 1,791 passed, only the two pre-existing,
unrelated `BUG-046`/`BUG-047` failures remain.

## Finding this piece produced

`BUG-049` (P3, open) — the fake server's background thread leaves 5
uncollectable GC objects at interpreter shutdown. Does not fail any test.
Investigated, not root-caused: confirmed introduced by this work (A/B'd),
confirmed *not* caused by the server in isolation (isolated repro showed
zero garbage) — an interaction with the rest of the session.

## Reference

ADR `../DECISION_2026-08-25_sanity_model_and_execution.md`, D6, D4.
