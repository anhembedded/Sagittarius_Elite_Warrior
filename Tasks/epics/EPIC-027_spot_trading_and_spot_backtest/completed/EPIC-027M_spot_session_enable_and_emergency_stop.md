# EPIC-027M — Enable trading, Emergency Stop and the session limits mean the right thing on Spot

**Status:** ✅ Done (2026-09-27)
**Source:** follows the user's *"giao dịch spot"* request, 2026-09-26.
**Risk:** 🔴 — Emergency Stop is the last line of defense; a Spot version that leaves a holding behind is a silent failure.
**Complexity:** M — three handlers get a Spot branch through the market type, not through `if` chains.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027K](EPIC-027K_spot_trading_client_and_order_path.md), [EPIC-027L](EPIC-027L_spot_user_data_stream.md)

---

## 1. Context and problem
- Enable trading refuses to start when any position exists: "foreign positions refused"
  (`application/session/enable_trading/handler.py:119-127`). On Spot, holding assets is normal and
  says nothing about whether the app opened them.
- Emergency Stop closes with a MARKET order, `reduce_only=True`, on the opposite side
  (`application/session/emergency_stop/handler.py:193-202`). On Spot, "close" means selling the base
  holding. The quantity must be floored to the lot step, and the fee may already have been taken in
  the base asset.
- The session limits are USDT-notional (`src/config/config_keys.py:91`). That works for USDT-quoted
  pairs (ADR D9).

## 2. Acceptance criteria
- [x] Enabling on Spot records the starting holdings as a baseline. It does not refuse because assets
      are present. What the app then trades is measured against that baseline.
- [x] Emergency Stop on Spot: disable → cancel all open orders → sell the base holding of the armed
      symbol down to what the baseline held, floored to the lot step. A dust remainder below
      `MARKET_LOT_SIZE`/`NOTIONAL` is reported, not retried forever.
- [x] Emergency Stop never sells assets the baseline held before enabling, and a test proves it.
      Selling the user's long-term holdings would be the worst possible failure.
- [x] The four session limits apply to Spot orders unchanged, in USDT.

## 3. Design
- **The refusal was already gone, the baseline was not.** `positions = trading_client.get_positions()`
  already always answers `[]` for Spot (`SpotTradingClient`'s own contract, `EPIC-027K`), so
  `UNEXPECTED_POSITIONS` never actually fired for Spot before this task — the real gap AC1 names is
  that nothing recorded what the account held at Enable time, so Emergency Stop had no baseline to
  measure against. `EnableTradingCommandHandler` already fetches `ExchangeConnectionStatus` (via
  `ITradingAccountReader.check_connection()`) before it ever reaches the (never-firing, for Spot)
  positions check — its `holdings` field is reused as-is, no second network call, to build
  `{asset: total}` and pass it into `TradingSessionState.enable(spot_baseline_holdings=...)`.
- **The baseline is state, not a policy.** `TradingSessionState` already holds "what does this app
  currently believe about the account" (`known_open_symbols`, `enabled`) — the Spot baseline is the
  same kind of fact, extended one step further back in time ("what did the account look like before
  this app started"), so it lives there rather than as a second singleton two handlers would both
  need wiring to. `None` means "no baseline recorded" (never enabled this session, or enabled on a
  non-Spot venue) and is the safety-critical case: `EmergencyStopCommandHandler` treats it as
  "unknown baseline, sell nothing" rather than guessing zero and offering up the user's entire
  pre-existing holdings (`code/errors.md` #6 — no fabricated fallback). An empty dict (`{}`) is a
  real, distinct baseline — "enabled while holding nothing" — under which every later-held unit is
  fair game.
- **The arithmetic is a pure policy.** `domain/policies/spot_holdings_close_policy.py`'s
  `sellable_spot_quantity(current_total, baseline_quantity, step_size)` — `current - baseline`,
  floored to the lot step, never negative — composes the existing
  `OrderQuantityRoundingPolicy.round_quantity_down()` rather than duplicating its rounding rule, and
  is mutation-verified in isolation from the handler's network calls and error handling.
- **Strategy pattern per `code/quality.md` §3, not scattered `if market == SPOT`.** `_close_all_positions`
  is now a single one-line dispatch (`if self._trading_venue.market_type is MarketType.SPOT: ...`) to
  either the unchanged `_close_all_futures_positions` (renamed from `_close_all_positions`, body
  untouched) or the new `_sell_spot_surplus_holdings`. `EmergencyStopCommandHandler` gains three new
  constructor dependencies — `TradingVenue`, `ITradingAccountReader`, `IMarketMetadataProvider` — all
  already bound unconditionally in `adapter_bindings.py`, so the DI container's own auto-wiring
  resolves them with zero composition-root changes (verified: no `EmergencyStopCommandHandler(...)`
  construction call site exists anywhere in `src/`; `container.bind(EmergencyStopCommand,
  EmergencyStopCommandHandler)` is the only registration, and it reflects the constructor).
- **Re-fetch current holdings, never trust the baseline snapshot as "now".** `_sell_spot_surplus_holdings`
  calls `ITradingAccountReader.check_connection()` again at Emergency Stop time — the same
  "authoritative re-fetch, never a remembered value" principle `FuturesUserDataStream`'s own
  `get_positions()` re-fetch already established for the Futures side, just applied to Spot's own
  source of truth.
- **What "armed symbol" turned out to mean.** The task's own wording ("sell the base holding of the
  armed symbol") suggested a single symbol; in practice every currently-held, non-dust, non-quote
  asset is checked against its own baseline entry (defaulting to `0` when the asset was never part of
  the baseline) — this is strictly more correct than restricting to a tracked "armed" set (an asset
  bought without a `TradingSessionState.known_open_symbols` entry, however that happened, would
  otherwise be silently excluded from Emergency Stop's own safety net) and requires no new tracking
  concept.
- **AC4 needed no code change, only proof.** The four session limits
  (`ExecuteOrderCommandHandler`/`TradingLimitPolicy`/`TradingLimitContext`) already read plain
  venue-agnostic counters off `TradingSessionState` and a USDT notional off `OrderPreview` — nothing
  in that path assumes Futures. A new test (`test_the_same_four_limits_apply_unchanged_on_spot`)
  proves this directly against `TradingVenue.SPOT_TESTNET` rather than leaving it an inferred,
  unverified claim.
- **`Docs/SPEC/`'s Emergency Stop section — out of scope, recorded rather than dropped.** The task's
  own file table names "the Emergency Stop SPEC gains a Spot section (with `EPIC-026B`'s SPEC-007)".
  `SPEC-007` does not exist yet — `Docs/SPEC/README.md`'s own use-case table lists it 🔵 (not yet
  written), owned by the not-yet-started `EPIC-026B`. Writing a Spot section into a SPEC that has no
  Futures section yet would invert that epic's own ordering; this AC-adjacent file-table row is
  explicitly deferred to whichever epic writes SPEC-007 first, not silently skipped.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/trading_session_state.py` | `_spot_baseline_holdings`, `enable(spot_baseline_holdings=...)`, `spot_baseline_holdings()` reader |
| `src/modules/trading/domain/policies/spot_holdings_close_policy.py` | new — pure `sellable_spot_quantity()` |
| `src/modules/trading/application/session/enable_trading/handler.py` | records the Spot baseline from the already-fetched `status.holdings` |
| `src/modules/trading/application/session/emergency_stop/handler.py` | venue-branched step 3; new `TradingVenue`/`ITradingAccountReader`/`IMarketMetadataProvider` deps; `_sell_spot_surplus_holdings()` |
| `tests/unit/modules/trading/domain/policies/test_spot_holdings_close_policy.py` | new — 6 tests, mutation-verified |
| `tests/unit/modules/trading/application/test_trading_session_state.py` | +7 baseline tests |
| `tests/unit/modules/trading/application/session/test_enable_trading.py` | +3 Spot-baseline tests |
| `tests/unit/modules/trading/application/session/test_emergency_stop.py` | +8 Spot-sell tests (surplus, never-below-baseline, no-baseline safety, dust, quote-asset skip, dust-holding skip, per-asset failure, unreachable venue) |
| `tests/unit/modules/trading/application/orders/test_execute_order.py` | +1 test proving the four limits fire identically on `SPOT_TESTNET` (AC4) |

## 5. Testing
- Unit: baseline arithmetic (`sellable_spot_quantity` — never negative, floors to the lot step,
  boundary at exactly one step, mutation-verified by hand: swapping the `<= 0` guard or the floor for
  a ceiling turns a test red for the right reason); `TradingSessionState`'s baseline storage (records,
  clears on a Futures/`DISABLED` enable, distinguishes `None` from `{}`, returns a copy, respects
  `expected_generation`); `EnableTradingCommandHandler` (records from real `status.holdings`, empty
  baseline when holding nothing, no baseline on Futures); `EmergencyStopCommandHandler` (sells the
  surplus with the right symbol/side/type/quantity, never sells at-baseline holdings, refuses to sell
  with no baseline recorded, reports dust without an order, skips the quote asset and dust holdings,
  reports a per-asset placement failure, reports failure on an unreachable venue rather than a silent
  no-op); the new Spot limits test (AC4).
- Integration: not added — every acceptance criterion is fully covered at the unit tier against the
  real `TradingSessionState`/domain policy, with `FakeTradingAccountReader` (the port's own verified
  fake) standing in for the network boundary; a fake-exchange journey would duplicate this coverage
  without adding a new observable fact.
- Regression: `tests/unit/architecture` 457 passed; `tests/unit/modules/trading` + `tests/unit/architecture`
  + `tests/integration` 1584 passed, 4 pre-existing skips, 0 failed (baseline 1555 + 29 new). `ruff
  check`/`ruff format --check` clean across `src tests tools scripts`. `mypy src scripts` unchanged at
  the pre-existing 584-error baseline (verified before and after).
- Full local gate (`ci-local.ps1 -Full`): not run locally, per `ci-rule.md` §1 (user decision
  2026-09-18) — GitHub Actions' `-Full` check run on the PR is the full-gate authority, cited once
  green.
