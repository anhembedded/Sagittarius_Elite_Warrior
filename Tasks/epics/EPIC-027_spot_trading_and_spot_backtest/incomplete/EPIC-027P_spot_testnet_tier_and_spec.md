# EPIC-027P — A real Spot Testnet round trip is proven, and the Spot order lifecycle is a written SPEC

**Status:** 🟡 In progress (2026-09-28) — blocked on the user's own Spot Testnet run (AC5)
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
- [ ] The user runs the tier once and the output is pasted into this task file.

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
- Not run: the tier itself against a real Spot Testnet account (needs the user's own
  `BINANCE_SPOT_TESTNET_API_KEY`/`_SECRET`) — AC5.

## 6. Resume
- **Blocked on:** AC5 only — the tier's real round trip needs the user's own Binance Spot Testnet
  API key/secret, which no amount of further autonomous work can substitute for.
- **Everything else in scope is done and verified** (AC1–AC4, the HLD and SPEC-005 doc fixes):
  see §5 above.
- **Next executable action, once the user supplies credentials:** set
  `BINANCE_SPOT_TESTNET_API_KEY`/`_SECRET` (env or `src/config/secrets.local.json`, the same
  file the Futures tier already uses — `ADR D8` keeps the two venues' keys separate), set
  `SEW_TESTNET_TESTS=1`, and run
  `pwsh -NoProfile -File scripts/ci-local.ps1 -TestnetOnly`. Paste the resulting
  `===END_CI_LOCAL_RESULT===` block (or the log file's relevant excerpt) into this section, check
  off the final AC box, flip SPEC-012 (its own status line and its `Docs/SPEC/README.md` row)
  from 🟡 to ✅, move this file to `completed/`, and update the epic's README/TRACKING and
  `Tasks/ROADMAP.md` to close EPIC-027P (and, since it is the epic's last queued sub-task per
  `README.md`'s dependency chain, review whether `EPIC-027` itself is ready to close).
