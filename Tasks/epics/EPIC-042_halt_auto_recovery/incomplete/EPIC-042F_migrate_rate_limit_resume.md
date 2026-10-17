# EPIC-042F — The grid rate-limit auto-resume runs on the halt-recovery mechanism

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D6](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟡 — changes the state and the alerts a Spot owner sees during every rate-limit pause
**Complexity:** M — one reason, one probe whose clear is the pause's end, the retired counter
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042C](EPIC-042C_grid_halt_recovery.md)

---

## 1. Context and problem
`GridRateLimitPause` resumes a rate-limited Grid when the exchange's named pause ends (`MAX_AUTO_RESUMES`, consecutive, in memory). It is a second recovery mechanism with its own counter. The owner asked for the answer and a record, not the work ([decision D6](../DECISION_2026-10-17_halt_auto_recovery.md)).

## 2. Acceptance criteria
- [ ] Decide first, with the owner: does a rate-limited bot wait in `AWAITING_RECOVERY` (state and alerts change) or does the timer stay a `HALTED` special case?
- [ ] If migrated: `RATE_LIMITED` has a rule whose *clear* is the pause's end (the probe reads the gateway's pause), the consecutive counter is gone, the rolling budget applies, and the retired constants are deleted, not left beside it.
- [ ] A pause longer than `MAX_AUTO_RESUME_WAIT` still stays `HALTED` for a person.

## 3. Design
Not started. The differences that make it non-trivial are in the decision's §3.

## 3a. Reuse
To be filled when started.

## 4. Changes, per file
To be filled when started.

## 5. Testing
To be filled when started; the existing rate-limit tests are the oracle and are not weakened.

## 6. Docs touched
To be filled when started.
