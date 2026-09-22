# EPIC-026N — A watchdog on the user data stream: silence alerts, an exhausted reconnect budget disables trading

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 6; the user (2026-09-20): *"hãy cho
lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — it disables trading by itself; a false positive stops a healthy session, a false
negative leaves the app trading on stale truth.
**Complexity:** M — a heartbeat, two thresholds, one scheduled check, one command.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-004` §5 ("The network drops").
**Depends on:** [`EPIC-026M`](EPIC-026M_out_of_band_alerting.md)

---

## 1. Context and problem

Order truth comes only from the user data stream (`EPIC-021` ADR §4; `place_order` discards the
response, `futures_trading_client.py:85-107`). The stream delegates reconnection to python-binance
and, when the library's budget runs out, logs and stops (`futures_user_data_stream.py:119` and the
generation-fenced loop at `:245-290`). Nothing in the app then knows that its picture of fills and
positions has frozen; the strategy keeps sending orders on it. On Testnet that produced `BUG-096`'s
confusion; on mainnet it produces a position the app does not know it holds.

## 2. Acceptance criteria

- [ ] `IUserDataStream` exposes `last_message_at()`; the adapter updates it on every frame,
      including keep-alive pings.
- [ ] `StreamWatchdog` runs on the engine's scheduler every 10 s: silence longer than
      `trading.stream_silence_warning_s` (default 90) sends one alert (`EPIC-026M`) and shows a
      banner; silence longer than `trading.stream_silence_disable_s` (default 300), or the adapter
      reporting `stopped` while trading is enabled, dispatches `DisableTradingCommand` with a
      named reason `STREAM_LOST` and alerts again.
- [ ] The watchdog never enables anything, and never restarts the stream itself (the adapter
      owns that); `SPEC-004` §5 gains the row.
- [ ] The Emergency Stop is **not** triggered by silence alone (a stale picture is not a loss);
      the ADR's alternative table records why.
- [ ] A drill: `main.py stream-drill` blocks the stream for 6 minutes and shows the chain running,
      logged under `App.StreamWatchdog`.

## 3. Design

Heartbeat-and-deadline is the standard pattern; the scheduler is the engine's
(`ONBOARDING.md` §12.3 names it a kernel service), the check is a small application service in
`trading/application/session/`, and the action is the existing `DisableTradingCommand` (the
docstring at `disable_trading/handler.py:27` already calls disable "the recovery step after a
connection is lost mid-session" — this task makes something call it).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_user_data_stream.py` | `last_message_at()` |
| `src/modules/trading/adapters/binance/futures_user_data_stream.py` | Update on every frame; expose stopped state |
| `src/modules/trading/application/session/stream_watchdog.py` | The check and the two actions |
| `src/modules/trading/contracts/events/stream_silence_event.py` | Warning and lost events; `EventRegistry` rows |
| `src/modules/trading/application/session/disable_trading/{command,handler}.py` | Optional reason carried to the UI |
| `src/config/config_keys.py`, `app_config.json` | Two thresholds |
| `tests/unit/modules/trading/application/session/test_stream_watchdog.py` | Fake clock; warning at 90 s, disable at 300 s, stopped → disable; nothing when disabled |
| `Docs/SPEC/SPEC-004_….md` | §5 row |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Thresholds | unit with an injected clock | unit | one warning, one disable, no repeats |
| No action while off | unit | unit | silent |
| Drill on Testnet | `stream-drill` | human | banner, alert, trading off, log lines — pasted here |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
