# EPIC-035N — Invalid parameters are explained where they are

**Status:** ✅ Done (2026-10-08), its status-bar criterion superseded by `EPIC-035W`
**Source:** the owner's Spot Grid audit, 2026-10-08, finding L10 (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz); Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟢 — UI only, but it is the first thing the owner sees
**Complexity:** M
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** None
**Board:** the Plan panel puts a draft's parameters before its figures, a field with a verdict carries a stop or warning icon beside its sentence, the chart says "Grid not drawn: …", a Save names why Start is still blocked; the status-bar line is `EPIC-035W`'s and was not built.

---

## 1. Context and problem
Audit L10, from the owner's screenshot: the refusal reason sits at the top of the Plan panel and is scrolled out of view; fields are not highlighted; Save accepts invalid parameters; the chart is silent about the missing grid overlay; the status bar reads "Market data: not live" while the chart is Live. Cited: `src/modules/bots/ui/bots_screen/`, the status bar (`src/shell/`). Verify each claim on the running app before coding. Relates to `EPIC-034F` (constraints on their field) and `EPIC-034G` (the chart's live state), which are Done: the task finds what they left.

**Claims re-verified on `1bad483` by rendering the Bots screen's `preview.py` offscreen and by a geometry test, 2026-10-08.**
- The reason "sits at the top of the Plan panel and is scrolled out of view": **holds, measured.** For a draft whose capital is above the balance, at 1366x768 the Capital error began 619 px down a 372 px scroll viewport (`test_the_reason_is_visible_without_scrolling_beside_its_field` red: `619 + 30 <= 372`), because the figures read-out (nine rows) and the readiness lines come first.
- Fields are not highlighted: **partly holds.** `EPIC-034F` already puts the sentence under the field ("Blocks Start: …"); nothing on the field itself said it was wrong.
- Save accepts invalid parameters: **holds, and is right for a draft** (a half-edited draft must be storable); what was wrong is that Save said "done" and nothing said Start would still refuse. Handled by the second option of the criterion.
- The chart is silent about the missing overlay: holds; `BotChartHost.draw(None)` drew an empty overlay and said nothing.
- The status bar "Market data: not live": not re-verified on the running app; **superseded by `EPIC-035W`** (its own text says so). Not built here.

## 2. Acceptance criteria
- [x] The reason appears beside the field and is visible without scrolling: a bot at rest (DRAFT, STOPPED) shows its parameters right after the count of what is left, then its steps, reasons and figures; a bot with a run keeps its figures first (`BotPlanPanel._arrange`). Evidence: `test_the_reason_is_visible_without_scrolling_beside_its_field` (red 619 + 30 > 372, green after), `test_the_parameters_of_a_bot_at_rest_come_before_its_figures`, `test_a_bot_with_a_run_shows_its_figures_first`.
- [x] The field is marked invalid: the platform's own stop icon (blocks Start) or warning icon (advice) beside the sentence, with the accessible name "Blocks Start" / "Advice"; no style sheet, no colour as the only signal. Evidence: `test_a_field_with_a_verdict_carries_a_sign_beside_its_sentence`, `test_the_sign_goes_when_the_verdict_does`.
- [x] Save says exactly what it saved and why Start is blocked: "Save …: done. Saved as they are. Start is still blocked: <the readiness message>", and only then. Evidence: `test_a_save_over_a_plan_start_refuses_says_so`, `test_a_save_of_a_plan_that_can_start_says_only_that_it_is_done`. Save is not refused: a draft may hold any parameters.
- [x] The chart shows "Grid not drawn: …" with the reason when the overlay is missing: the first refusing verdict, or that the market numbers are still being read, above the chart of a bot at rest (`BotDetail.overlay_note` → `BotsViewModel.chart_note` → `lblGridNotDrawn`). Evidence: `test_the_chart_says_why_no_grid_is_drawn`, `test_the_chart_says_nothing_while_the_grid_is_drawn`.
- [ ] ~~The status bar reflects the selected bot's own stream~~ — superseded by [`EPIC-035W`](../incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md) (its acceptance criterion 2 and its Context say so). Left out on purpose; not built, not tested here.

## 3. Design
QtWidgets only, OS theme, per `ui-presentation-rule.md`: the icons are `QStyle.StandardPixmap` (`SP_MessageBoxCritical`, `SP_MessageBoxWarning`), the note and the markers are plain labels, nothing is sized or styled by hand. Nothing runs on the UI thread that was not already there: the judgement is the existing debounced pure function, the Save note reads the detail already in memory. `BotPlanPanel` keeps one reorder method, guarded so a selection that changes nothing re-lays nothing. `preview.py` now shows the invalid state (a blocking verdict on Capital, advice on the range, the chart note).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/ui/bots_screen/bot_plan_panel.py` | `_arrange`, `index_of_parameters`, `index_of_figures` |
| `src/modules/bots/ui/kinds/grid/grid_panel.py` | the marker beside each field's sentence |
| `src/modules/bots/ui/bots_screen/{bot_detail,detail_effects,bots_view_model,bots_view}.py` | `overlay_note`, `chart_note`, the label above the chart |
| `src/modules/bots/ui/bots_screen/bots_presenter.py` | `_still_blocked`, the Save note |
| `src/modules/bots/ui/bots_screen/preview.py` | the invalid state |

## 5. Testing
Unit tier on the real presenter and view (`test_bots_invalid_parameters_are_explained.py`, nine tests; seven red before, the two "says nothing" locks passed before by design). One existing test adjusted: `test_without_a_chart_the_centre_says_how_to_get_one` now counts only visible labels (the hidden note is another label in the area). The preview was rendered offscreen before and after; after, the Capital field shows the stop icon and its sentence in view beside it. Not run: a real display (the owner's screenshot is the check).

## Implementation notes
- A Save of a bot with a run is not offered (only drafts and stopped bots save), so `_still_blocked` reads the detail of a bot at rest.
- The readiness lines now sit below the parameters for a bot at rest; its count ("Start: 1 thing left") stays at the top, and the field says the reason itself.

## Resume
Done. Nothing owed except `EPIC-035W` for the status bar.
