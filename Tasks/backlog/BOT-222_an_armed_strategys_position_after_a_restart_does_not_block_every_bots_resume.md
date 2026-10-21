# BOT-222 — An armed strategy's position after a restart does not block every bot's Resume

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** A position an armed strategy holds on a position venue is claimed by nobody, so after a restart it refuses every bot's Resume and Stop, the same O2/O12 contradiction `BUG-250` closed for bots.
**Source:** The review of PR #680 (Q3, 2026-10-21): "Is a strategy owner's position after a restart out of scope on purpose? If so, a backlog line would make that explicit." The coordinator asked for it to be filed the same day.
**Risk:** 🔴 — it changes which positions a closed order session may open over; a mistake admits a foreign position.
**Complexity:** M — the strategy owner has no tag-and-run-start ledger like a bot's, so what its claim would name is a design question first.
**Depends on:** None (`BUG-250` / #680 is merged).

---

## 1. Context and problem
`BUG-250` (#680) lets a Resume and the operator's Stop open a closed order session over a position when a claim on its symbol is backed by the exchange's tagged history (`PositionExplainer`, `src/modules/trading/application/session/position_explainer.py`). Only bots claim (`venue_position_claims`, `src/modules/bots/application/kinds/grid/grid_position_claims.py`). A strategy armed on a position venue (owner `strategy`) can hold a position across a restart; nobody claims it, so `NO_CLAIM` refuses every bot's Resume and Stop on that venue. That is existing behaviour, not a regression, but it is the same contradiction for another owner.

## 2. Acceptance criteria
- [ ] A decision records whether an armed strategy's position may be excused after a restart, and by what evidence (its orders' tag and the arm's start), or that it stays refused on purpose and why.
- [ ] If excused: a test on the composed app over the fake exchange arms a strategy, leaves its position across a restart and resumes a bot; a stray symbol and a size beyond the strategy's tagged history still refuse.
- [ ] The refusal's words name the strategy as the holder when it is the one blocking, not "no bot of this venue claims it".

## 3. Design
Open: the arm has no persisted run start, so the claim's evidence window must be recorded at arm time (a stored field) or the strategy stays out. Start from `OwnerPositionClaim` (one claim per owner run) and `PositionUnexplainedWhy` (one row per reason); `architecture-rule.md` §7.2.1 says the seam exists, so the variant is a local change once the evidence is decided.

## 3a. Reuse
`OwnerPositionClaim`, `PositionExplainer`, `PositionUnexplainedWhy`, `refusal_words`: used. A UI need: none.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/strategy/` (arm record) | store the arm's start so a claim can name it |
| a strategy-side claim source | the strategy module's claims, passed by the same Resume and Stop path |
| `src/modules/trading/contracts/session_block_words.py` | a reason that names a strategy holder |

## 5. Testing
Integration on the fake Futures exchange (`ci-rule.md` §2): arm, restart with the session closed, resume a bot; negative cases above. Not run.

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` (the claims paragraph), `Docs/SPEC/SPEC-014_run_a_grid_bot.md` (the restart row), the strategy module's SPEC if one exists.
