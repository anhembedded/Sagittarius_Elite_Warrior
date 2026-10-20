# BOT-207 — `OwnerBooks` is within the 15-public-method guideline again, its read side apart from its lifecycle side

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** `OwnerBooks` has 17 public methods against the guideline of 15 (`architecture-rule.md` §4): two fixes (`BUG-203`, `BUG-233`) each added one with the excess noted only in a bug report. Split its read side from its lifecycle side so the next fix does not make it 18.
**Source:** the independent reviewer's retroactive review of `BUG-233` (PR #623), 2026-10-20: "`OwnerBooks` now has 17 public methods against the 15-method limit. BUG-203 accepted 16 and this PR accepts 17, both only as a note in a bug report. No backlog task records the split" (https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/623#issuecomment-6292491102). The delivery coordinator asked for it to be filed, not implemented.
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
- [ ] `OwnerBooks`, and every class the split creates, has at most 15 public methods.
- [ ] No behaviour changes: the existing `OwnerBooks` unit tests, the `BUG-203` and `BUG-233` regression tests (unit and integration) pass unchanged in what they assert.
- [ ] One lock still guards the registry and the departed-symbols set: no read can observe a book half-way through a fill (a test applies a fill from one thread while another reads `facts` and `position_of`, and sees the book before or after the fill, never between).
- [ ] No caller among the seven other files that use `OwnerBooks` (`owner_position_deriver`, `position_state_reconciler`, `trading_session_state`, `owner_inventory_deriver`, `register_owner_budget/handler`, `i_owner_book`, `venue_event_emitter`) reaches through one object to another (Law of Demeter, `code/quality.md` §10).
- [ ] `TradingSessionState`'s count is stated in the implementation notes, split here if it is on the same seam, otherwise filed as its own task.

## 3. Design
The likely split, to be confirmed against the callers when the task is taken: the registry (`_by_tag`, `_lock`, the buffers and `install`/`clear`/`clear_owner`/`apply_*`/`record_sent`) stays `OwnerBooks`; the read side moves behind a read-only view built over the same registry and lock, either `OwnerBookReads` or a read port in `contracts/` if the callers need an interface (P7: a port only for a consumer that exists). `take_departure` and `has_owner_on` belong to the departed-symbols concern of `BUG-233`; whether they are a third small class (`OwnerDepartures`) or stay with the reads is decided from who calls them (`position_state_reconciler`). The split follows the CQRS shape the application layer already uses (`architecture-rule.md`); the view shares the lock rather than copying state, so there is still one source of truth (`domain-truth-rule.md`).

Not decided here: the names, and whether `take_departure`'s consume-on-read is kept (it is a command-query mix that `BUG-233` accepted as documented; a split is the moment to ask whether it should be two methods).

## 3a. Reuse
`None: no UI need`. Application need: the CQRS read-view shape of the existing application services (`.claude/rules/architecture-rule.md`); no catalog row applies (`.claude/rules/capabilities.md` lists UI and support mechanisms).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/owner_books.py` | Registry and lifecycle stay; the read methods move out. |
| New file beside it | The read view over the same registry and lock. |
| The seven files listed in §2 | Take the read view where they only read. |
| `tests/unit/modules/trading/application/` | A concurrency test for the shared lock; existing tests move with the methods they cover. |

## 5. Testing
Unit tier (`ci-rule.md` §2) for each criterion; the `BUG-203` / `BUG-233` regression tests are the proof that behaviour is unchanged. A public-method-count guard is not added: the architecture guards already read `>15` (`C7`) and the review row catches it.

## 6. Docs touched
None, because there is no `Docs/MODULES/trading/` folder (the review of `BUG-233` K10 recorded this); the module docstring of `owner_books.py` is updated with the split.
