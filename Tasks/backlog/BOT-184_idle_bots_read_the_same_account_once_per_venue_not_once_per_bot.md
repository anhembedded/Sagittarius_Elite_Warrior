# BOT-184 — An idle bot costs the venue about 25 request weight a minute instead of 175: the beat's reads are shared by the bots of a venue

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** `EPIC-029J1b` measured an idle Futures bot at 175 request weight a minute (mostly two `positionRisk` reads and two mark reads a beat), which is why five bots a venue is the cap; reading the account's positions once per beat for all bots would let the cap rise.
**Source:** `EPIC-029J1b` §5a measurements (2026-10-17).
**Risk:** 🟡 — the risk and mark watches are what notice a liquidation risk and a crossed stop; sharing their reads must not make a bot judge on a stale figure.
**Complexity:** M — one reader per venue per beat with a freshness bound, behind the existing watches' ports.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `EPIC-029J1b`.

---

## 1. Context and problem
On the fake Futures exchange's `WeightMeter`, one idle bot over a minute (12 beats of `CHECK_EVERY_SECONDS`, a tick a second) spent 175 weight: `GET /fapi/v3/positionRisk` 120 (two reads a beat, 5 each), `premiumIndex` 24, `openOrders` 12, `openAlgoOrders` 12. It scales linearly with the bots: five bots 875 (52 % of the gate's 1,680 line), ten bots 1,750 (past it), twenty bots 3,500 (past the exchange's own 2,400). A `positionRisk` without a symbol is one request for the whole account (weight 5), so N bots reading it once per beat would cost 25 a minute in all.

## 2. Acceptance criteria
- [ ] Measured with `tests/integration/modules/bots/test_many_bots_on_one_venue_cost_on_the_fake_exchange.py`: N idle bots of one venue cost no more than 2 × the cost of one, for N = 1, 5, 20.
- [ ] Each bot's liquidation-risk and mark-exit watch still judges on a reading no older than today's worst case (one beat).
- [ ] The cap (`MAX_ACTIVE_BOTS_PER_VENUE`) is raised only by the owner, from the new figures.

## 3. Design
Not written.

## 3a. Reuse
`ExchangeCallPolicy` / `RateLimitGate` (not a second limiter), `GridRiskWatch`, `FuturesMarkSource`.

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts.

## 6. Docs touched
`Docs/MODULES/bots/10-quality.md` (the cap row), `Docs/MODULES/bots/06-runtime.md`.

## Implementation notes (written when done)
