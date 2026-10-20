# BOT-201 — The Start refusal for a venue that holds a RECOVERING bot may be stricter than it needs to be

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** A Start is refused while another bot of the venue is `RECOVERING` because opening the session was said to reconcile it; since `BOT-183` and `BOT-197` no opening wakes it, so the reason, and perhaps the refusal, is stale.
**Source:** the review of #603 (`BOT-197`), 2026-10-20, relayed by the coordinator session: "pre-existing, not this PR's ... worth a backlog task for the owner".
**Risk:** 🟡 — the refusal is a real-money guard; removing or loosening it changes which bots may start, so the owner decides, and the wording alone is safe to fix.
**Complexity:** S — one predicate, two prose sites; the owner's decision comes first.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `BOT-183`, `BOT-197` (merged).

---

## 1. Context and problem
At `d39b065` (`master-warrior`), `src/modules/bots/application/services/lifecycle/other_active_bot.py` → `venue_recovering` (docstring, lines 86-90) justifies refusing a Start while another bot of the venue is `RECOVERING` with "opening it reconciles every RECOVERING bot of the venue and lets it trade". `Docs/SPEC/SPEC-015_run_the_bots_headless.md:79` says the same twice: the refusal "names the venue's RECOVERING bots, because opening the order session reconciles them", and `--resume-recovering` "opens the venue's order session, which reconciles the bots". Since `BOT-183` (a session opened for one bot resumes no other) and `BOT-197` (a person's manual order or strategy arm resumes none), no opening reconciles a `RECOVERING` bot except its own Resume or `--resume-recovering`. The stated reason is false. Whether the refusal still protects something else (a RECOVERING bot's unreconciled orders on the same venue, the five-per-venue cap, budget registration) has not been checked.

## 2. Acceptance criteria
- [ ] The owner decides, with options: (a) keep the refusal and correct its stated reason; (b) drop it, so a Start beside a `RECOVERING` bot is allowed. Recommended: (a) until (b) is shown safe, since it is a real-money guard.
- [ ] Whatever is decided, `venue_recovering`'s docstring and `SPEC-015` §3a/§6 state the true reason, and `ADR 038 O2` / `DECISION_2026-10-19_a_session_opened_for_one_bot_resumes_no_other.md` are linked.
- [ ] If (b): a composed-app test shows a Start on a venue holding a `RECOVERING` bot leaves that bot `RECOVERING`, and the cap and budget accounting still count it.

## 3. Design
Not written; the owner's choice comes first.

## 3a. Reuse
`None: no UI or application need` until the owner chooses (b).

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts.

## 6. Docs touched
`Docs/SPEC/SPEC-015_run_the_bots_headless.md`, `Docs/MODULES/bots/06-runtime.md` if the refusal changes.

## Implementation notes (written when done)
