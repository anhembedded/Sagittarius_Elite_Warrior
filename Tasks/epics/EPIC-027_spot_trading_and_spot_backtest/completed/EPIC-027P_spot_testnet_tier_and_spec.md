# EPIC-027P — A real Spot Testnet round trip is proven, and the Spot order lifecycle is a written SPEC

**Status:** ✅ Done (2026-09-29)
**Source:** follows the user's *"giao dịch spot"* request, 2026-09-26; `testing-rule.md` §1 (`tests/testnet/`).
**Risk:** 🟡 — touches a real exchange (testnet); must never make someone else's CI red.
**Complexity:** M — an opt-in tier, a SPEC, the user's own confirmation run.
**Epic (optional):** [EPIC-027](../README.md)
**SPEC (optional):** a new `Docs/SPEC/` use case for the Spot order lifecycle
**Depends on:** [EPIC-027K](EPIC-027K_spot_trading_client_and_order_path.md) through [EPIC-027O](EPIC-027O_live_ui_for_spot.md)

---

## 1. Context and problem
- `tests/testnet/` is opt-in twice: `SEW_TESTNET_TESTS=1` plus Futures Testnet credentials
  (`tests/testnet/conftest.py:1-54`). `test_order_lifecycle.py:76-166` proves a Futures round trip
  and closes with `reduce_only=True`.
- No Spot tier exists, and no SPEC describes a Spot order.
- **`EPIC-027O`'s independent reviewer (PR #288) flagged two documentation facts this task's own
  scope already touches but its file list did not mention** — carried forward here rather than left
  to fall through the crack between tasks:
  - `Docs/HLD/11_desktop_workbench.md:44` still lists the RAIL dock's panels as "positions, open
    orders, session, strategy, last signal" — no mention of the Holdings dock `EPIC-027O` added,
    which replaces Positions on a Spot venue.
  - `Docs/SPEC/SPEC-005_place_a_manual_order.md` §2 precondition 2 ("the venue is Futures Testnet")
    is now false: `EPIC-027O` made Spot manual submission (BUY, and SELL gated on a real holding) a
    fully working path, not merely a domain-layer refusal.
  - The reviewer also noted the new fake-Spot-exchange integration test
    (`test_spot_manual_order_pipeline_against_fake_server.py`, `EPIC-027O`) drives only a BUY through
    the wire, not a SELL — lower-risk than it sounds since `spot_order_payload_mapper.py` has no
    side-conditional branch (BUY/SELL map identically), but this task's own round-trip test is the
    natural place to add that missing SELL leg against the real fake exchange.

## 2. Acceptance criteria
- [x] `tests/testnet/spot/` runs only with its own opt-in flag and Spot Testnet keys. Without them it
      skips with a stated reason and never fails the gate.
- [x] It proves a round trip: BUY a small MARKET quantity → holding appears (read through
      `SpotAccountReader.check_connection().holdings`, the same read the Holdings table is driven by —
      not the user data stream, which carries no holdings snapshot of its own) → SELL it
      back → holding returns to baseline. It asserts invariants (`FILLED`, back to baseline), never
      prices, and cleans up in `finally`.
- [x] A SPEC describes the Spot order lifecycle, with the tests that prove it listed under
      "Proven by".
- [x] `Docs/HLD/11_desktop_workbench.md`'s RAIL dock panel list names the Holdings dock (Spot) beside
      Positions (Futures).
- [x] `Docs/SPEC/SPEC-005_place_a_manual_order.md` §2's venue precondition reflects that Spot manual
      submission is a real, working path (BUY, and SELL gated on a real holding), not just Futures.
- [x] The user runs the tier once and the output is pasted into this task file.

## 3. Design
- Mirror the Futures tier's structure and its opt-in gate. Keep separate credentials (ADR D8).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/testnet/spot/conftest.py`, `tests/testnet/spot/test_spot_order_lifecycle.py` | new tier |
| `Docs/SPEC/SPEC-012_place_a_spot_order.md` + `Docs/SPEC/README.md` | new use case |
| `Docs/HLD/11_desktop_workbench.md` | RAIL dock panel list names Holdings (Spot) beside Positions |
| `Docs/SPEC/SPEC-005_place_a_manual_order.md` | §2 precondition updated for Spot manual submission |

## 5. Testing
- `tests/testnet/spot/conftest.py` + `tests/testnet/spot/test_spot_order_lifecycle.py`: ruff
  `check`/`format --check` clean; confirmed skipping cleanly (`1 skipped`, stated reason) without
  `SEW_TESTNET_TESTS=1`.
- `tests/unit/architecture/test_spec_index_is_consistent.py`: 43/43 passed — SPEC-012's index row,
  required sections and every cited test path (including the new testnet file) verified to exist.
- Full `tests/unit/architecture` suite: 464/464 passed (god-file and duplication ratchets
  unaffected by this slice — no `src/` files touched).
- `mypy` at the real gate invocation (`src`/`scripts` only, from repo parent dir): unchanged at the
  584-error baseline; the new `tests/testnet/spot/` files are outside the gate's scanned paths
  (`tests/` is never part of it), matching the existing Futures testnet test's own pattern.
- **AC5 — run against the user's own real Spot Testnet account (2026-09-29):**
  ```
  tests\testnet\spot\test_spot_order_lifecycle.py::test_market_buy_then_sell_returns_the_holding_to_baseline PASSED
  tests\testnet\test_connection.py::test_account_is_reachable PASSED
  tests\testnet\test_order_lifecycle.py::test_dry_run_is_accepted PASSED
  tests\testnet\test_order_lifecycle.py::test_market_order_fills_and_closes PASSED
  4 passed in 9.99s
  ```
  A real MARKET BUY (`0.0002 BTC`) and MARKET SELL round-tripped on Binance Spot Testnet
  (`BTCUSDT`), holding returned to baseline within one lot step, Futures Testnet tier unaffected.
  Two real defects surfaced and fixed during this run, both merged to `master-warrior` before the
  green run above:
  - **`BUG-137`** (PR #290): `EnvFirstCredentialsProvider.resolve()` didn't strip whitespace from
    env-var-sourced credentials — a trailing `\n` from a shell paste reached the signed request's
    `X-MBX-APIKEY` header and surfaced as a misleading generic `NETWORK` failure.
  - **`BUG-138`** (PR #291, alongside a NETWORK-failure logging fix): Binance's real `BTCUSDT`
    `MARKET_LOT_SIZE` filter reports `stepSize`/`minQty` of `"0.00000000"` — Binance's own
    convention for "no restriction, `LOT_SIZE` applies instead" — but `spot_metadata_parser.py`
    only normalized to `None` (triggering the `LOT_SIZE` fallback) when the filter was entirely
    *absent*, not when present-but-zero. The unrounded SELL quantity (a BUY fill net of its fee)
    was sent with more decimal precision than the real `LOT_SIZE` step allows, and Binance rejected
    it with `-1013 Filter failure: LOT_SIZE`. Confirmed live via the user's own
    `Invoke-RestMethod` call against `testnet.binance.vision`'s `exchangeInfo`.

## 6. Resume
- **Done (2026-09-29).** All five acceptance criteria met; see §5 for the AC5 evidence.
- Two real defects surfaced by the user's own troubleshooting of the live run were fixed and
  merged ahead of the green run recorded in §5: `BUG-137` (PR #290) and `BUG-138` (PR #291).
  Both are filed under `Tasks/bug_report/completed/` except `BUG-138`, which was fixed per the
  user's explicit instruction to skip filing a separate report for that pass (its root cause and
  fix are recorded in PR #291's description and this file's §5 instead).
- SPEC-012 flipped back to ✅ built and proven (its own file and `Docs/SPEC/README.md`'s row) —
  the real Spot Testnet round trip in its §8 is now proven, closing the one gap the independent
  review of PR #289 had found.
- This was `EPIC-027`'s last queued sub-task; the epic itself is now closed — see its own
  `README.md`.
