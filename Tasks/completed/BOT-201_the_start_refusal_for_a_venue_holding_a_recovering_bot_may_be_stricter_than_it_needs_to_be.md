# BOT-201 — The Start refusal for a venue that holds a RECOVERING bot may be stricter than it needs to be

**Status:** ✅ Done (2026-10-20)
**Priority:** P3
**Board:** The Start refusal for a venue holding a `RECOVERING` bot stays (owner decision a, 2026-10-20) but its stated reason was false since `BOT-183`/`BOT-197` (opening the session resumes no other bot); the true reason, that such a bot's orders and budget are reconciled only by its own Resume so nothing new starts beside unverified exposure, is now in the docstring, the refusal text and the specs. No behaviour change.
**Source:** the review of #603 (`BOT-197`), 2026-10-20, relayed by the coordinator session: "pre-existing, not this PR's ... worth a backlog task for the owner".
**Risk:** 🟡 — the refusal is a real-money guard; removing or loosening it changes which bots may start, so the owner decides, and the wording alone is safe to fix.
**Complexity:** S — one predicate, two prose sites; the owner's decision comes first.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `BOT-183`, `BOT-197` (merged).

---

## 1. Context and problem
At `d39b065` (`master-warrior`), `src/modules/bots/application/services/lifecycle/other_active_bot.py` → `venue_recovering` (docstring, lines 86-90) justifies refusing a Start while another bot of the venue is `RECOVERING` with "opening it reconciles every RECOVERING bot of the venue and lets it trade". `Docs/SPEC/SPEC-015_run_the_bots_headless.md:79` says it at line 79: the refusal "names the venue's RECOVERING bots, because opening the order session reconciles them", and at line 83 `--resume-recovering` "opens the venue's order session, which reconciles the bots". Since `BOT-183` (a session opened for one bot resumes no other) and `BOT-197` (a person's manual order or strategy arm resumes none), no opening reconciles a `RECOVERING` bot except its own Resume or `--resume-recovering`. The stated reason is false. Whether the refusal still protects something else (a RECOVERING bot's unreconciled orders on the same venue, the five-per-venue cap, budget registration) has not been checked.

## 2. Acceptance criteria
- [x] The owner decides, with options: (a) keep the refusal and correct its stated reason; (b) drop it, so a Start beside a `RECOVERING` bot is allowed. Recommended: (a) until (b) is shown safe, since it is a real-money guard.
- [x] Whatever is decided, `venue_recovering`'s docstring and `SPEC-015` §3a/§6 state the true reason, and `ADR 038 O2` / `DECISION_2026-10-19_a_session_opened_for_one_bot_resumes_no_other.md` are linked.
- [x] If (b): a composed-app test shows a Start on a venue holding a `RECOVERING` bot leaves that bot `RECOVERING`, and the cap and budget accounting still count it.

## 3. Design
### Decision (2026-10-20): option (a), keep the refusal and correct its stated reason
Decided by: the owner's pre-approved recommendation, relayed by the coordinator session `session_016sGQHsRy729Fp4cY1cTXfu` (ONBOARDING §7, "Settle an owner decision that carries a recommendation"). A veto reverts the wording; the code is untouched.

| Option | Effect | Verdict |
| :--- | :--- | :--- |
| (a) Keep the refusal, correct the reason | No behaviour change; every message and document says what the refusal really keeps | **Chosen** (the recommendation) |
| (b) Drop it | A Start beside a `RECOVERING` bot is allowed | Not chosen: it touches a real-money guard and no test shows it safe; criterion 3 of this task says what would have to be shown first |

What the refusal still protects, read in the code at `d2c7cad`:
- **Not the reason it gave.** A Start opens the session announced as opened for the starting bot (`BotEventRouter.on_switch` passes `event.opened_for`; `GridFacts._apply_switch` reconciles a `RECOVERING` bot only for its own id or for `None`), so no Start resumes a waiting bot. Its own Resume or `run --resume-recovering` does (ADR 038 O2; [the decision of 2026-10-19](../../epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-19_a_session_opened_for_one_bot_resumes_no_other.md)).
- **Not the per-venue cap or the symbol rule.** `BotSlot.is_active` is true for `RECOVERING`, so `venue_is_full` and `other_active_bot` already count the waiting bot; they hold without this refusal.
- **Unreconciled orders and unregistered budget.** A restart leaves a `RECOVERING` bot with its saved orders (and on a position venue its position) possibly standing on the exchange. Boot only reads them (`BotBootRecovery`, a `RecoveryReport`); the reconcile that matches them, registers the bot's owner budget with the session (`GridReconciler`, `GridFacts.reconcile_recovering`) and puts back a missing protective stop runs only on the bot's own Resume. A Start would add a new bot's orders to an account whose existing exposure nothing has verified. On a position venue the session's first opening already refuses a position no registered owner claims (`SessionReadyResult.UNEXPECTED_POSITIONS`, recorded in `EPIC-029J1b`); that is the session's own check, not shown here to cover every case.
- **Not shown:** that a Start beside a `RECOVERING` bot is unsafe in a way the cap, the lease and the owner budgets do not already stop. That is the question option (b) would need a composed-app test for (criterion 3), and it is left open on purpose.

## 3a. Reuse
None: the owner chose (a); no code is added.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/lifecycle/other_active_bot.py` | module and `venue_recovering` docstrings state the true reason and link the decision |
| `src/modules/bots/application/services/readiness/readiness_assessment.py` | the refusal the user sees (`RUN_VENUE_RECOVERING`) and the `RunFacts.venue_recovering` comment |
| `src/modules/bots/application/use_cases/start_bot_for_host/handler.py` | the module docstring and the sentence of the refusal that asks for `--confirm-venue` |
| `Docs/SPEC/SPEC-015_run_the_bots_headless.md` | §6, the two statements (`bot start` refusal; `--resume-recovering`) |
| `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/OPERATIONS/headless_runbook.md`, `Docs/VOCABULARY/README.md`, `Docs/MODULES/bots/06-runtime.md` | the same reason wherever it was repeated |
| two test docstrings, one pinned sentence | `test_bot_readiness_assessment.py` pins the new refusal text; the others only restate the reason |

## 5. Testing
The readiness test pins the new refusal sentence; the Start-refusal composed-app test and the `venue_recovering` unit tests pass unchanged (the behaviour is the same).

## 6. Docs touched
`Docs/SPEC/SPEC-015_run_the_bots_headless.md`, `Docs/MODULES/bots/06-runtime.md` if the refusal changes.

## Implementation notes (written when done)
- Behaviour is unchanged: the predicate `venue_recovering` and the readiness item `RUN_VENUE_RECOVERING` are as before; only words changed. No log call was added or changed.
- Noticed and left alone: the docstring of `stop_bot_for_operator/handler.py` still says opening the session reconciles every bot of the venue, which `BOT-183` made untrue for a stop (the handler's own message already says the other bots keep waiting). It is not this refusal, so it is not edited here.
