# BUG-045 — The Sanity tier makes live network calls to `api.binance.com` on every CI run

**Reported:** 2026-08-25, found by the first run of the rebuilt Sanity tier (`EPIC-009`).
**Severity:** 🟡 **P2** — no incorrect application behaviour, but every Sanity run
depends on the public internet and on Binance being reachable. Green CI has been
partly measuring the network. Directly violates the tier's own written contract.
**Status:** 🔴 Open

## Symptom

Resolving certain handlers through the real DI container performs an HTTPS
request during construction:

```
DependencyResolutionError: Failed to resolve 'exchange_client' for
SyncMarketDataCommandHandler: HTTPSConnectionPool(host='api.binance.com',
port=443): Max retries exceeded with url: /api/v3/ping
```

Three use cases are affected — every one that depends on `exchange_client`:

- `SyncMarketDataCommand` → `SyncMarketDataCommandHandler`
- `RepairDataGapCommand` → `RepairDataGapCommandHandler`
- `ListAvailableSymbolsQuery` → `ListAvailableSymbolsQueryHandler`

## Root cause

`container.resolve(...)` constructs the handler, which constructs
`PythonBinanceClient`, whose `Client(api_key, api_secret)` pings
`/api/v3/ping` at construction time. The DI graph therefore reaches the network
merely by being resolved — no dispatch required.

The Sanity fixtures patch `AsyncClient` and `BinanceSocketManager`, which are the
**websocket** entry points only. The REST `Client` was never patched.

## Why this went unnoticed

It only fails where outbound HTTPS is blocked. On a developer machine with
internet the call succeeds in milliseconds and the test passes, so the tier has
been making a live third-party request on every run for as long as these tests
have existed — visible to nobody.

It was found the moment the tier ran in an environment without direct internet.

## Contract violated

`.agents/rules/ci-rule.md` §6, level 3: *"**Sanity:** real app boot, DI wiring and
QML construction only; no user action, background dispatch or **network**."*

The retired `Tasks/reference/sanity_legacy/test_database_screen_di_sanity.py`
resolves `SyncMarketDataCommand` and `ListAvailableSymbolsQuery` directly, so
this has been true of the shipped tier, not only of the rebuilt one.

## Fix

Not a mock. `EPIC-009`'s **D6** is the intended resolution: run a local fake
Binance server and point the real `python-binance` client at it by base URL, so
production's entire adapter stack still executes and only the endpoint moves.
Substituting `IExchangeClient` would be the cheap option and is explicitly
rejected — it is the shape that produced
[`BUG-026`](../completed/BUG-026_shutdown_probe_missing_stream_historical_klines_implementation.md)
and [`BUG-027`](../completed/BUG-027_seeded_market_data_repository_missing_seven_port_methods.md).

Worth deciding separately: whether `PythonBinanceClient` should ping at
construction time at all. A constructor that performs I/O makes the whole DI
graph un-resolvable offline, which is a design smell independent of testing.

## Interim state

`tests/sanity/test_composition_root.py` records these three in `_BLOCKED_BY_BUG`
with a reference to this file. The other 14 use cases stay guarded. The entries
are removed when D6 lands — they are a recorded debt, not an exemption.
