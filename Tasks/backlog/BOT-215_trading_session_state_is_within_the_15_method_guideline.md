# BOT-215 — `TradingSessionState` is within the 15-public-member guideline, its switch, its leases and its position bookkeeping apart

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** `TradingSessionState` has 18 public members against the guideline of 15 (`architecture-rule.md` §5); [BOT-207](../completed/BOT-207_split_owner_books_by_read_and_lifecycle_side.md) noted it and left it, because it is on other seams than the owner books.
**Source:** the independent reviewer's review of `BUG-233` (PR #623) reported the count; `BOT-207` (2026-10-21) found it on a different seam and filed it here.
**Risk:** 🟡 — the session state is read from the order pool, the websocket and the session handlers under one lock; a split must keep one lock.
**Complexity:** M — three groups of members, one lock to share.
**Depends on:** None.

---

## 1. Context and problem
At `137fe0a`, `src/modules/trading/application/trading_session_state.py` → `TradingSessionState` has 18 public members: the switch and the stop (`generation`, `stop_in_progress`, `begin_stop`, `end_stop`, `live_submission_guard`, `enable`, `disable`, `switch_epoch`), the symbol leases and the position bookkeeping (`claim_symbol`, `release_symbol`, `lease_holder`, `open_position_count`, `reconcile_position`, `read_all`), and the rest (`spot_baseline_holdings`, `install_owner_book`, `time_since_last_order`, `record_order_sent`). More than 15 public members forces a split (`architecture-rule.md` §5; review checks C7, D6).

## 2. Acceptance criteria
- [ ] `TradingSessionState` and every class the split creates has at most 15 public members.
- [ ] No behaviour changes; one lock still guards what it guarded.

## 3. Design
Not written. The `BOT-207` split shows the shape: shared state and its lock in a data holder, each group a class over it.

## 3a. Reuse
`OwnerBookState` and `OwnerBookReads` (`BOT-207`) as the model.

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts.

## 6. Docs touched
None expected: there is no `Docs/MODULES/trading/` folder.
