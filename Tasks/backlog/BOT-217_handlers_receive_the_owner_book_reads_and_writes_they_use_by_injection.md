# BOT-217 — Handlers receive the owner books' read and write sides they use, not the session state that holds them

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** After the `OwnerBooks` split ([BOT-207](completed/BOT-207_split_owner_books_by_read_and_lifecycle_side.md)) the application handlers still reach the books through `session_state.owner_book_reads.x()` and `session_state.owner_books.x()`; injecting the side each uses removes the navigation through the state.
**Source:** the review of `BOT-207` (PR #667), round 1, finding 2: the criterion "no caller reaches through one object to another" was deferred, not met.
**Risk:** 🟡 — twelve constructors of money-limit handlers change; behaviour must not.
**Complexity:** M — wiring in `trading/composition/venue_assembly.py` and the handlers' tests.
**Depends on:** `BOT-207`.

---

## 1. Context and problem
`session_state.owner_book_reads.facts(...)` is one attribute over `session_state.owner_books.facts(...)`, the shape `code/quality.md` §10 (Law of Demeter) names. The handlers that use the books are `ExecuteOrderCommandHandler`, `RegisterOwnerBudgetHandler`, `EmergencyStopHandler`, `TradingSessionService`, `position_state_reconciler`, `owner_position_registrar` (all under `trading/application/`).

## 2. Acceptance criteria
- [ ] Each of those takes the `OwnerBooks` or `OwnerBookReads` it uses as a constructor argument, and none reads `session_state.owner_books` or `owner_book_reads`.
- [ ] No behaviour changes; the `BUG-203` and `BUG-233` tests pass unchanged.

## 3. Design
Not written. The venue assembly already builds `TradingSessionState` once per venue and can hand each handler the side it needs; one lock stays (`OwnerBookState`).

## 3a. Reuse
`OwnerBookReads`, `OwnerBooks` (`BOT-207`).

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts.

## 6. Docs touched
None expected: there is no `Docs/MODULES/trading/` folder.
