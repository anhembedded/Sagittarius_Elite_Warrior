# EPIC-040A — The Grid's backtest page is pinned by tests and preview frames before anything moves

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"Bạn tạo epic luôn, viết từng task, đánh giá design từng task"* ("create the epic, write each task, assess each task's design")
**Risk:** 🟢 — tests and preview frames only; no product code changes
**Complexity:** S — the page's states are few and already named in its presenter
**Epic:** [EPIC-040](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem
The Grid's backtest page (`src/modules/bots/ui/kinds/grid/backtest/`, 8 files, about 1,190 lines) is about to be split across a kind-neutral workbench (040D) and a Grid adapter (040F). The 039B oracle pins the simulator's figures, but nothing pins what the page shows in each state:
- idle with a reason;
- running and Cancel;
- refused for missing candles, with Sync offered;
- refused for missing funding, with "Run without funding" offered;
- a Spot result and a Futures result with its funding and liquidation lines;
- cancelled;
- a different bot selected mid-run.

Without that pin, 040F can lose a state silently.

## 2. Acceptance criteria
- [ ] Each state above has a presenter-level test that drives the real presenter and view on the fake exchange's candles and asserts the visible words and which buttons are enabled.
- [ ] `preview.py` gains one frame per state (Spot and Futures), so the owner can compare before and after.
- [ ] Each test is shown to fail when its state's wording or button state is changed (mutation note in the implementation notes).

## 3. Design
**Characterisation tests first** (Feathers' "pin before you move"). They test behaviour at the page's public surface (the presenter's inputs, the view's visible text and actions), never private methods, so they survive 040F's move unchanged. That is the whole value of this task.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Pin at the presenter/view surface (chosen) | Survives the move. 040F runs the same tests against the workbench-hosted page. |
| Pin with screenshot diffs | Rejected: brittle across fonts and platforms; the conformance suite already guards layout. |
| Skip and rely on the oracle | Rejected: the oracle covers numbers, not states, and the states are where 039J and 039K added behaviour (funding refusal, brackets wait). |

**Risk:** low. The only trap is testing through private helpers, which would tie the tests to the code 040F deletes. Review check: tests import only the presenter, the view's public names and the preview frames.

## 3a. Reuse
- **Test fixtures:** used the existing grid fake-exchange fixtures (`tests/integration/modules/bots/grid_fake_exchange.py`) and the `preview_frames.py` pattern from `EPIC-039J`.
- **Application code:** none, because the task only adds tests and preview frames.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/modules/bots/ui/kinds/grid/backtest/test_grid_backtest_states.py` | New: one test per state |
| `src/modules/bots/ui/kinds/grid/backtest/preview.py` | One frame per state |

## 5. Testing
Unit tier (presenter and view with a real Qt widget, offscreen). Each criterion maps to one test; mutation checks recorded. The commit tier and the architecture suite also run.
