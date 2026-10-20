# BOT-209 — The Plan dock says where the bot stands once, and lists the kind's checks instead of a wall of text

**Status:** ✅ Done (2026-10-20)
**Board:** The Plan dock has one status banner (the first thing left before Start with where to fix it, how the last run ended, or "Ready to start"), a checks list (errors and warnings first, the passed ones folded into one "N checks passed" row, the whole sentence as a tooltip) and a one-line hint with a "Use N grids" button under a field, instead of the readiness lines, the "What the kind says" text wall and the five-line inline paragraph; each check is titled where the kind makes it (`Verdict.title`, `Verdict.summary`); words and figures unchanged.
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu) for the owner, 2026-10-20: "Giải quyết cho tui mấy cái này xem, nhìn nó chấp vá ghê, tự tìm giải phát nhé, tui cũng không rành UI" (sort these out, it looks patched together; find the solution yourself, I don't know UI well), after two screenshots of the Plan dock following BOT-206 (#634).
**Risk:** 🟢 — presentation only: no rule, threshold or figure changes; two defaulted fields on `Verdict` and one required part on `Advice`; tests that read the old labels read the banner and the list.
**Complexity:** M — a banner, a checks list, a pure status function, titles and one-line summaries at their sources, the Grid editor's hints split into their own file, four preview frames.
**Epic (optional):** none; stays inside the Plan dock (PR #642 is on the Backtest tab).
**SPEC (optional):** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** BOT-206 (the property table), EPIC-034F/H (field hints, readiness).

---

## 1. Context and problem
After BOT-206 the Plan dock of a Futures Testnet Grid draft (ETHUSDT) showed, in three places and four shapes, what is one fact (at `3cf7960`, `bot_plan_panel.py`):
1. a wall under the table, "What the kind says about these parameters:" and about 20 lines of `verdict_line` text ("OK: … (thinnest step 0.00382572…)") with the one warning among them;
2. the same thin-step warning twice: a five-line paragraph under Grids and again in the wall;
3. status scattered: "Draft — L14 SELL: the request failed…", "Start: 1 thing left" with its icon, the steps, and the blocker as a bullet at the foot of the editor;
4. *Margin mode* and *Liquidation (est.)* read as loose lines, the liquidation gap with raw decimals ("503.1053");
5. the table's last row cut where the wall began.

## 2. Acceptance criteria
- [x] One status banner under the bot's name: the first thing left before Start with where to fix it (and a count of the others), else "Connecting…", else "Ready to start"; the exchange's notes and the last run's note are lines under it; a bot with a run says how it ended or shows nothing. "Start: N things left" and the foot-of-editor bullet are gone as separate texts; the three steps stay as the table's Readiness rows.
- [x] The kind's verdicts are a list of checks: one row per check with the platform's icon, a short title and a one-line finding; errors, then warnings, first; every passed check folded into one "N checks passed" row that opens and stays open; the whole sentence with its exact numbers is the row's tooltip.
- [x] The hint under a field is one line (the check's own summary, rounded), with a "Use N grids" button on Grids when the check names a count; the long paragraph is a tooltip, on no label.
- [x] Each check's words are written where the check is made: a title per constraint and per Futures risk code, a summary in every `Advice`.
- [x] Nothing overlaps or is cut at 1024×700, 1366×768 and 1920×1080.
- [x] Preview frames: a draft blocked by a held position, a draft with a thin-step warning, a ready draft, a running bot.

## 3. Design
**Pattern.** An inline message bar (Qt Creator / VS Code's "info bar") for the one state; a Windows "task list" (icon, title, finding) for the checks, with the passed ones counted, as IDEs fold green results. Stock Qt only: the kit's `NoticeBar` (a styled frame, the platform's message icon, a wrapped label) and a `QTreeView` over a `QStandardItemModel` configured by the Engine's `configure_item_view`, like BOT-206's table.
**Words at their source.** `Verdict` gains `title` and `summary` (both default `""`); `Advice` gains a required `summary` (so no advice can be added without its one-line form, the contract `BUG-210` set). A constraint's title lives on its `GridConstraint` row and `run_checks` writes it on the verdict; the Futures risk codes have `FUTURES_PLAN_TITLES`; a hint shows `summary or reason`, the list shows the same.
**One source.** The hint under a field and the list's row read the same `summary`; the long `reason` is a tooltip in both. The list still shows a check the field also shows: it is the complete record, the hint is the pointer in context.
**No button in the banner.** `test_no_push_button_of_the_mode…` and `ui-presentation-rule.md` §6 forbid a push button repeating a command of the mode; "Show log" is the Log dock's View toggle and "Fix next item" a Bots command, so the banner's sentence says where (`→ edit Capital`, `→ Bots → Retry venue account`) and the runtime's own text already says "see the log". The Grids field's "Use N grids" is the kind's own per-field helper, which the rule exempts, as Suggest from ATR is.
**Split.** `grid_panel.py` crossed 400 lines; the sign, line and button under each field moved to `grid_field_hints.py` → `FieldHints`.

## 3a. Reuse
- Banner: moved `NoticeBar` from `backtesting/ui/notice_bar.py` to `support/ui_kit/notice_bar.py` (its own docstring said a second consumer moves it); `show_notice` re-words it, the capability catalog row is generated.
- Table: `configure_item_view`, `spec_table.displayed_text_at`, the BOT-206 row-height approach (extracted to `wrapped_rows.py`, used by both lists).
- Words: `verdict_line` (detail), `readiness_words` (`item_sentence` split out of `_item_line`), `bot_facts` (`state_word`, `note`), `Advice` / `Figures`.
- Icons: the platform's `QStyle.StandardPixmap` through `NoticeKind` and `marker_icon`.
- Searched `capabilities.md` for banner, notice, message bar, list of checks: `MessageBar` is the mode-level failure bar (`INotifier`), not a dock's state.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/domain/verdict.py`, `grid_advice.py`, `grid_advice_texts.py`, `grid_checks.py`, `grid_exit_checks.py` | `Verdict.title`/`summary`; `Advice.summary` and the six one-line summaries |
| `bots/domain/grid/grid_constraints.py`, `futures_grid_checks.py`, `grid_evaluation.py`, `application/.../exchange_rules.py` | a title per constraint, per risk code and per one-off verdict |
| `support/ui_kit/notice_bar.py` (moved), `backtesting/ui/backtest_top_panel.py` | the shared notice bar; one import |
| `bots/ui/bots_screen/plan_checks.py`, `plan_checks_view.py`, `plan_status.py`, `plan_status_banner.py`, `wrapped_rows.py` | new: the checks, their list, the status sentence, the banner, the shared row height |
| `bots/ui/bots_screen/bot_plan_panel.py`, `bots_view_model.py`, `bot_detail.py`, `detail_effects.py`, `bot_facts.py`, `readiness_words.py`, `plan_property_grid.py` | the panel's new top and bottom; the model holds `PlanChecks` |
| `bots/ui/kinds/grid/grid_field_errors.py`, `grid_field_hints.py` (new), `grid_panel.py`, `grid_liquidation.py` | one-line hints, the "Use N grids" button, the liquidation gap to the cent |
| `bots/ui/bots_screen/plan_dock_frames.py`, `preview.py`, `preview_frames.py` | four frames; the old previews feed the model checks |
| tests | see 5 |

## 5. Testing
Unit tier, QtWidgets offscreen; the conformance suite is the integration proof.
| Criterion | Proof |
| :--- | :--- |
| errors and warnings first, passed folded | `test_plan_checks.py`, `test_plan_checks_view.py` |
| the blocker in the banner, the last run under it | `test_plan_status.py`, `test_plan_dock_frames.py::test_the_blocker_is_in_the_banner_once_and_the_old_texts_are_gone` |
| no duplicate advice text, one source | `test_plan_dock_frames.py::test_a_thin_step_is_one_headline_under_grids_and_in_the_list_never_a_paragraph` |
| "Use N grids" | `test_plan_dock_frames.py::test_the_hints_button_proposes_the_count…` |
| no clipping at the three sizes | `test_plan_dock_frames.py::test_nothing_overlaps_or_is_cut_at_the_three_window_sizes` (4 frames × 3 sizes) |
| every constraint titled | `test_grid_constraints.py::test_every_constraint_is_named_for_a_list_of_checks` |
| conformance | `tests/integration/presentation/ui/` booted suite |

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (the Plan dock's banner and checks), `Docs/HLD/11_desktop_workbench.md` §11.2.1 (Plan row), `.claude/rules/capabilities.md` (generated row).

## Implementation notes (written when done)
See the pull request for the gate evidence. Frames: `Tasks/completed/BOT-209_assets/` (`python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_dock_frames <frame> --png <path> [--size WxH]`).
Decisions the owner may veto: the banner has no button (rule, §3); the list repeats a check the field also shows (one source, §3); "Margin mode" and "Liquidation (est.)" stay rows of the editor's form, the BotKindPanel contract unchanged.
