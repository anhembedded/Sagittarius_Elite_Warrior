# SPEC-004 — Turn live trading on, and off

- **Status:** ✅ built and proven
- **Actor:** trader
- **Origin:** `EPIC-021G`, with `BUG-088` (a concurrent state change mid-reconciliation) and
  `BUG-089` (a second click landing on an in-flight toggle).
- **Surfaces:** the Trading screen's Enable/Disable toggle. The Settings screen only **reads**
  this state — it refuses a venue change while trading is on and says where to turn it off.

## 1. Trigger

*"I am ready to let this app send real orders — and I want to know what my account already
holds before it does."*

## 2. Preconditions

1. The configured trading venue is Futures Testnet. Any other venue means trading is off at the
   configuration level and no toggle can override it.
2. Credentials resolve and the exchange is reachable — SPEC-003's check, which this use case runs
   again itself rather than trusting an earlier answer.
3. Live trading is **off**. It always is at start-up: this state is never persisted across runs.
   It is the one setting this app deliberately does not remember.

## 3. Main flow

1. The actor clicks Enable on the Trading screen.
2. The app disables the toggle for the duration — a second click cannot begin a second attempt.
3. The app runs the connection check. Not reachable, or reachable-but-unusable, ends it.
4. The app reads the account back: open positions, and open orders.
5. The app compares that against what it believes. If the exchange holds a position this app has
   no record of, it **refuses** — it does not adopt the position, and it does not close it.
6. The app re-checks that nothing else changed the session while steps 3–5 were on the network.
   If something did — most importantly an Emergency Stop — this attempt loses and answers
   refused.
7. On success the app allows live submission, records what it reconciled, and the toggle reads
   Enabled.
8. Disabling is the mirror and is simpler: it always succeeds, immediately, and needs no network.

## 4. What must be true afterwards

- When the toggle reads Enabled, the app's belief about open positions and open orders came from
  **the exchange, moments ago** — not from a cached value, and not from an earlier session.
- When it reads Disabled, no order can be submitted live from any surface. Every submission path
  checks this same session state.
- Every refusal names itself: the venue is disabled, the connection is not ready, there are
  unexpected positions, or a concurrent change superseded the attempt. There is no bare
  `False`, and the screen shows the actor a sentence for each.
- An Emergency Stop that lands during an enable **wins**. Silently turning trading back on right
  after an Emergency Stop would defeat the button.
- Disabling never refuses, which is why there is no `DisableTradingResult` to read.
- The session's three facts — enabled, orders sent this session, symbols believed open — are read
  as one frozen snapshot. A screen can never observe half of a change made by the websocket
  thread.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| The venue is not Futures Testnet | Refused: `TRADING_VENUE_DISABLED` | The configuration-level gate, checked here and again at every submission |
| The connection check does not come back ready | Refused: `CONNECTION_NOT_READY` | Includes Hedge mode — "reachable but not usable" is already a named connection failure (SPEC-003) |
| The exchange holds a position this app never sent | Refused: `UNEXPECTED_POSITIONS`, with what was found | The actor decides what to do about it. Adopting it silently would make the app's limits meaningless; closing it silently would trade without being asked |
| An Emergency Stop, a disable, or another enable lands mid-reconciliation | Refused: `SUPERSEDED_BY_CONCURRENT_STATE_CHANGE` | `BUG-088`. Reconciliation succeeding does not mean nothing else happened while it ran |
| The actor clicks the toggle twice | The second click does nothing; the first attempt's result is the one applied | `BUG-089`. The button is disabled while busy, and a result from a superseded action is fenced |
| The network drops mid-reconciliation | Refused, with the failure reported; trading stays off | Off is the safe end state, and it is the one the app defaults to |

## 6. What this use case does NOT promise

- **No symbol lease.** Turning trading on does not reserve anything. Nothing stops a manual order
  on a symbol a strategy is armed on; `ITradingSession`'s docstring records that the lease is
  Phase 2's, when `strategy` becomes its first consumer.
- It does not stay on. Closing the app turns it off, because this state is never persisted.
- It does not promise the reconciled picture stays true. It is a snapshot at enable time; the
  account can change underneath, and the app's `known_open_symbols` is deliberately conservative
  — a symbol is marked open the moment an order for it is *sent*, before any fill confirmation,
  because over-blocking a second order is safer than under-blocking one.
- It does not cancel or close anything. That is Emergency Stop (SPEC-007, planned), which
  disables, cancels every open order, closes every position, then reads the account back to
  confirm — and reports each of those three steps separately, because a partial stop is a real
  outcome the actor must see.

## 7. Ports and modules it exercises

`trading`: `ITradingSession` — `snapshot()`, `enable()`, `disable()`, `emergency_stop()` — plus
`EnableTradingResult` and `EnableTradingBlockReason` as the published answer. Reconciliation
reads through `ITradingAccountReader`; the connection gate is SPEC-003's `IAccountSnapshot`.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| Every block reason, including the concurrent-change generation check | `tests/unit/modules/trading/application/session/test_enable_trading.py` | unit |
| Disable always succeeds and needs no network | `tests/unit/modules/trading/application/session/test_disable_trading.py` | unit |
| Both implementations of the port answer the same way | `tests/unit/modules/trading/contracts/test_trading_session_contract.py` | contract |
| The toggle's async ownership: one action at a time, stale results fenced | `tests/unit/presentation/ui/screens/trading/test_trading_presenter_toggle.py` | unit |
| Settings refuses a venue change while trading is on | `tests/unit/presentation/ui/screens/test_settings_venue_controls.py` | unit |
| Turning it on against a real account | **the user runs it**: with Futures Testnet credentials, click Enable on the Trading screen and confirm the reconciled positions shown match the Testnet web UI | human |
