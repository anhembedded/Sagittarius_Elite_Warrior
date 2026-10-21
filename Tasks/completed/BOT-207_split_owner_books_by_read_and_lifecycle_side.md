# BOT-207 — `OwnerBooks` is within the 15-public-method guideline again, its read side apart from its lifecycle side

**Status:** ✅ Done (2026-10-21)
**Board:** `OwnerBooks` (17 public methods) is split into `OwnerBooks` (lifecycle and writes, 10) and `OwnerBookReads` (what is asked of the books, 8) over one `OwnerBookState` and one lock, so a read still never sees a book half-way through a fill; callers that only read take the read side through `TradingSessionState.owner_book_reads`. No behaviour changed. `TradingSessionState` (18) is a different seam and is filed as [BOT-215](../backlog/BOT-215_trading_session_state_is_within_the_15_method_guideline.md).
**Source:** the delivery coordinator, 2026-10-21, after the owner's "OK làm 5 task 1-5 luôn": split OwnerBooks by read side and lifecycle side, behaviour unchanged. The task itself came from the independent reviewer's retroactive review of `BUG-233` (PR #623), 2026-10-20: "`OwnerBooks` now has 17 public methods against the 15-method limit. BUG-203 accepted 16 and this PR accepts 17, both only as a note in a bug report. No backlog task records the split" (https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/623#issuecomment-6292491102). The delivery coordinator asked for it to be filed, not implemented.
**Risk:** 🟡 — `OwnerBooks` guards every budgeted owner's book under one lock and is reached from the trading session, the reconciler and the venue event emitter; a split that lets a read and a write take different locks would let a fill and a budget check disagree.
**Complexity:** M — the reads move out of one class, the lock and the `_by_tag` dict stay shared; no behaviour changes.
**Depends on:** None.

---

## 1. Context and problem
At `5e7d00f`, `src/modules/trading/application/owner_books.py` → `OwnerBooks` has 17 public methods (the module also holds `OwnerShare`, `OwnerEventBuffer` and `_HeldFill`, which are small and outside this count):

| Side | Methods |
| :--- | :--- |
| Lifecycle and writes (8) | `open_buffer`, `close_buffer`, `install`, `clear`, `clear_owner`, `record_sent`, `apply_fill`, `apply_end` |
| Reads (9) | `holder_of`, `has_owner_on`, `facts`, `position_of`, `shares`, `agrees_with_last_report`, `cross_check_owner`, `cross_check`, and `take_departure` (a read that also consumes, by design: it answers one flat report, `BUG-233`) |

The guideline: more than 15 public methods per class forces a split (`.claude/rules/architecture-rule.md` §4; review checks C7, D6). The class went over twice without a task to repay it: `BUG-203` (16) and `BUG-233` (17), each accepted in its bug report only. The review of `BUG-233` also reports `TradingSessionState` at 18; that class is a neighbour and is in this task's scope only to the extent of the note in §3.

## 2. Acceptance criteria
- [x] `OwnerBooks`, and every class the split creates, has at most 15 public methods.
- [x] No behaviour changes: the existing `OwnerBooks` unit tests, the `BUG-203` and `BUG-233` regression tests (unit and integration) pass unchanged in what they assert.
- [x] One lock still guards the registry and the departed-symbols set: no read can observe a book half-way through a fill (a test applies a fill from one thread while another reads `facts` and `position_of`, and sees the book before or after the fill, never between).
- [x] No caller among the twelve other files under `src/` that use `OwnerBooks` reaches through one object to another (Law of Demeter, `code/quality.md` §10): `trading/composition/venue_assembly.py`, `trading/contracts/i_owner_book.py`, `trading/adapters/binance/venue_event_emitter.py`, and under `trading/application/`: `owner_position_deriver`, `owner_inventory_deriver`, `owner_position_registrar`, `position_state_reconciler`, `trading_session_state`, `orders/execute_order/handler`, `session/register_owner_budget/handler`, `session/trading_session_service`, `session/emergency_stop/handler`. Several already reach it through `session_state.owner_books.<method>`, the case this criterion targets.
- [x] `TradingSessionState`'s count (18) is stated in the implementation notes; it is on another seam (the switch, the stop, the symbol leases), so it is filed as its own task.

## 3. Design
Decided from the callers (§2's list), as the task asked. `OwnerBookState` (`owner_book_state.py`) is the shared data and the one lock; it has no behaviour. `OwnerBooks` keeps the lifecycle and the writes: `open_buffer`, `close_buffer`, `install`, `clear`, `clear_owner`, `record_sent`, `apply_fill`, `apply_end`, and `take_departure`. `take_departure` stays on this side, not with the reads: it consumes the departed-symbol mark (`BUG-233`), a command that answers one flat report, and its only caller (`position_state_reconciler`) already pairs it with the writes' world. Its consume-on-read is kept as `BUG-233` accepted it (behaviour does not change here); splitting it into a read and a clear is a decision for a change that wants behaviour to move. `OwnerBookReads` (`owner_book_reads.py`) holds `holder_of`, `has_owner_on`, `facts`, `position_of`, `shares`, `agrees_with_last_report`, `cross_check_owner` and `cross_check`, over the same state, each under the same lock. `OwnerShare` moved with `shares`.

`TradingSessionState` builds `OwnerBooks` and holds `owner_book_reads = owner_books.reads`; a collaborator that only reads names `owner_book_reads`, so none writes through a read handle or reads through a write one, and none navigates `owner_books.reads.x()`. The access is still `session_state.<collaborator>.<method>`, the depth every other collaborator of the state has; handing each handler its collaborator directly would change those twelve constructors and is not this task.

No port was added for the read side (P7: no consumer needs an interface; the callers are concrete application code).

## 3a. Reuse
`None: no UI need`; the CQRS read-view shape of the application layer (`architecture-rule.md` §4).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/owner_book_state.py` | new: the shared state and lock |
| `src/modules/trading/application/owner_book_reads.py` | new: the read side, `OwnerShare` |
| `src/modules/trading/application/owner_books.py` | lifecycle and writes only; `reads` |
| `trading_session_state.py` | `owner_book_reads` |
| `position_state_reconciler.py`, `orders/execute_order/handler.py`, `owner_position_registrar.py`, `session/register_owner_budget/handler.py`, `session/trading_session_service.py`, `session/emergency_stop/handler.py` | reads go through `owner_book_reads` |
| tests (12 files) | read calls go to `reads` / `owner_book_reads`; assertions unchanged |

## 5. Testing
`tests/unit/modules/trading/application/test_owner_book_reads.py`: each side at most 15 public methods; the two sides hold no method of each other; a read sees a write; and **a read waits for a fill in progress** (a book whose fill is held half-way: `facts` asked meanwhile answers only after it, from the book after the fill) - red when `facts` takes a lock of its own, and when the reads are built over a state of their own. The `BUG-203` and `BUG-233` regression tests, the `OwnerBooks` tests and the integration tests pass with their assertions unchanged; only the receiver of a read call changed.

## 6. Docs touched
None, because there is no `Docs/MODULES/trading/` folder; the module docstring of `owner_books.py` names the split.

## Implementation notes
Public method counts after the split: `OwnerBooks` 10 (nine methods and the `reads` property), `OwnerBookReads` 8, from 17. `TradingSessionState` has 18 (`generation`, `stop_in_progress`, `begin_stop`, `end_stop`, `live_submission_guard`, `enable`, `spot_baseline_holdings`, `disable`, `switch_epoch`, `install_owner_book`, `read_all`, `open_position_count`, `time_since_last_order`, `record_order_sent`, `claim_symbol`, `release_symbol`, `lease_holder`, `reconcile_position`): the switch and stop, the symbol leases and the position bookkeeping are three seams other than the books, so it is [BOT-215](../backlog/BOT-215_trading_session_state_is_within_the_15_method_guideline.md).
