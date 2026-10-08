# EPIC-035N — Invalid parameters are explained where they are

**Status:** 🔵 Planned
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L10 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟢 — UI only, but it is the first thing the owner sees
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None

---

## 1. Context and problem
Audit L10, from the owner's screenshot: the refusal reason sits at the top of the Plan panel and is scrolled out of view; fields are not highlighted; Save accepts invalid parameters; the chart is silent about the missing grid overlay; the status bar reads "Market data: not live" while the chart is Live. Cited: `src/modules/bots/ui/bots_screen/`, the status bar (`src/shell/`). Verify each claim on the running app before coding. Relates to `EPIC-034F` (constraints on their field) and `EPIC-034G` (the chart's live state), which are Done: the task finds what they left.

This task is specified briefly: it is Phase 3 — Alerting and transparency. The full acceptance criteria are written, and each audit claim re-verified against the code, when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] The reason for an invalid parameter appears beside the field and is visible without scrolling.
- [ ] The field is marked invalid.
- [ ] Save is refused for a parameter that cannot ever run, or says exactly what it saved and why Start is blocked.
- [ ] The chart shows "Grid not drawn: …" with the reason when the overlay is missing.
- [ ] The status bar reflects the selected bot's own stream (`EPIC-035A`), not a global flag.

## 3. Design
QtWidgets only, OS theme, per `ui-presentation-rule.md`; a preview in `preview.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/` | as the criteria require |
| `src/shell/ (the status bar)` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- a presenter test per criterion (red before)
- a `preview.py` screenshot of the invalid state

Not run yet.

## Resume
Not started.
