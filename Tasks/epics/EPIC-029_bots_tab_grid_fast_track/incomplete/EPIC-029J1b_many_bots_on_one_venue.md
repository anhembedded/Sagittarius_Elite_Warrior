# EPIC-029J1b — Several bots run on different symbols of one venue, each within its own budget

**Status:** 🔵 Backlog — after J1a; sliced in detail when it starts
**Source:** [`PRO-006`](../../../proposal/PRO-006.md) §4.3 "After the fast track", accepted by the user on 2026-10-03 (*"Oki, duyệt"*); split from `EPIC-029J` on 2026-10-17, when the owner chose J1a first (*"còn chuyện multibot thì làm J1a trước đi"*).
**Risk:** 🟡 — concurrency across several actors and several budgets on one account and one request-weight budget.
**Complexity:** M — lift the per-venue cap, measure tick fan-out and request weight, aggregate the budget across the bots of a venue.
**Epic:** [EPIC-029](../README.md)
**Depends on:** [`EPIC-029J1a`](../completed/EPIC-029J1a_one_active_bot_per_venue.md) (one active bot per venue, done). `EPIC-029H` is not awaited (owner, 2026-10-17).

---

## 1. Context and problem
J1a made the cap one active bot per venue (`other_active_bot`). Two bots on one venue are still refused, though the entity, ids, store, tags and budgets are already per bot. This task lifts the per-venue cap for bots on **different symbols** of the venue and proves isolation. The symbol lease (trading's, per venue) stays the rule that keeps two bots off one symbol.

What J1a's audit found that this task must settle (evidence in J1a's notes):
- **A per-venue request-weight gate exists** (`ExchangeCallPolicy` / `RateLimitGate`, `exchange_call_policy.py`, `EPIC-035D`, `BUG-216`): it closes the venue's requests to the minute's end at 70 % of the exchange's weight and for a rate limit's or ban's stated pause, for every caller on the venue. So a closed gate already refuses every bot of the venue. What is open is the *bots'* reaction (each bot halts `RATE_LIMITED` separately, `grid_rate_limit_pause.py`) and a weight budget shared between bots *before* the 70 % line; build on the gate, not beside it.
- **The order pacer is per bot** (`MonotonicOrderPacer`, built per executor), so two bots of one venue do not space their orders against each other.
- **The owner budget's caps apply to each bot's own budget**, not to the sum of the bots of a venue.
- **Latent risk carried from `EPIC-042E`:** `--resume-halted` touches no other state only while no second bot can be active beside a HALTED one on its venue; its Resume opens the venue's order session, whose switch-on reconciles every RECOVERING bot of that venue. Several bots on one venue re-open the question whether a halted-bot resume may reconcile a RECOVERING bot the owner left for `--resume-recovering` (O2).

## 2. Acceptance criteria
- [ ] Several bots run on different symbols of one venue; each one's orders, fills and PnL are attributed by its tag and never by another's.
- [ ] Starting a bot on a symbol another bot holds is refused, naming the holder (the lease).
- [ ] Tick fan-out to N bots is measured (N = 1, 5, 20) before the cap is raised; the result is recorded and the chosen cap justified by it.
- [ ] Request weight of N bots on one venue is measured on the fake exchange's `WeightMeter` against the existing `RateLimitGate`; whether a weight budget shared before the 70 % line (or venue-wide pacing) is needed is decided from it, and a rate limit met by one bot makes its neighbours halt `RATE_LIMITED` too, not only be refused at the gate.
- [ ] An Emergency Stop halts every bot on that venue and none on the other (proved for one bot per venue by J1a; here for N on a venue).

## 3. Design
Each bot keeps its own actor (ADR D9); the event handlers route by tag. The measured fan-out decides whether events are filtered by symbol before queueing. The full per-file design is written when this task starts, against the tree as it is then.

## 3a. Reuse
`ExchangeCallPolicy` / `RateLimitGate` for request weight and rate limits (not a second limiter); `grid_rate_limit_pause` for the bots' pause.

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts; each criterion above maps to a unit or integration test, plus the Testnet tier where an exchange behaviour is involved.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
