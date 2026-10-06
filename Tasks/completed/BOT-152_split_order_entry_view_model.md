# BOT-152 — The order entry's view model splits what the presenter sets from what the view asks

**Status:** ✅ Done (2026-10-06)
**Source:** the review of PR #358 (EPIC-033R), 2026-10-05: `OrderEntryViewModel` grew to 30 public members, already over `PLR0904`'s 20, and the ratchet counts files, not members, so growth inside the file is invisible to it.
**Risk:** 🟢 — a split along a line the class already draws in its section comments
**Complexity:** S
**Epic:** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md) (the desks become the Trade mode in `EPIC-033I`)
**Depends on:** —

---

## 1. Context and problem
`src/modules/trading/ui/desk/order_entry/order_entry_view_model.py` holds three kinds of member under one class: reads (`entry`, `figures`, `can_take_order`, …), the user's intents (`set_price`, `request_submit`, `request_focus`, …) and the presenter's writes (`begin_symbol`, `set_context`, `show_result`, …). It is one `PLR0904` entry in `baseline_ruff_debt.json`, so adding a member does not move the ratchet.

## 2. Acceptance criteria
- [x] No class in the order entry's view model has more than 15 public methods (`architecture-rule.md` §5.4).
- [x] Its `PLR0904` entry leaves `baseline_ruff_debt.json`.
- [x] Every test of the order panel, its presenter and the desks passes unchanged in what it asserts.

## 3. Design
Split along the existing section comments: the state and its reads stay; the presenter's writes move behind a narrow object the presenter holds, so the view cannot call them. Name both after what they are, not after "helper".

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `order_entry/order_entry_view_model.py` | split |
| `order_entry/order_entry_presenter.py`, `desk_screen/desk_presenter.py` | hold the presenter-facing half |
| `tests/unit/architecture/baseline_ruff_debt.json` | lowered |

## 5. Testing
The existing order-entry and desk tests, unchanged in their assertions.

## Implementation notes (written when done)
- **Why three, not two.** Measured with `ruff --preview`: properties count, so the reads (12) and the user's intents (10) alone were 22 — moving only the presenter's 8 writes would have left the class over `architecture-rule.md` §5.4's 15. The split is along the three section comments: `OrderEntryViewModel` keeps the signals, `options` and the reads (14 public members); `OrderEntryUserIntents` (`vm.intents`, 10) holds what the view does; `OrderEntryPresenterWriter` (`vm.presenter_side()`, 8) holds what the presenter tells the panel. The three share one plain `OrderEntryState` (`order_entry_state.py`).
- **Behaviour kept.** The signals stay on the view model (`changed`, `submitRequested`, `bestPriceRequested`, `focusRequested`), so no connection moved; the intents and the writer emit through them. The constructor is unchanged.
- **Callers.** The view (`order_side_form.py`, `order_entry_panel.py`) calls `view_model.intents.*`; `OrderEntryPresenter`, `BestPriceFiller` and `FuturesSettingsChanger` take `view_model.presenter_side()` as `_writes`; `DeskPresenter` (F9) and both previews follow. Tests changed only in the receiver of the call, never in an assertion.
- **Guards added** (`test_order_entry_view_model.py`): each intent and write announces on the view model's signals (mutation: replacing the `focusRequested` wiring fails the intents test); each class stays at or under 15 public members; no view file mentions `presenter_side`.
- **Ratchet.** The file's `PLR0904` entry left `baseline_ruff_debt.json`.
- **Verification.** Commit tier (`ci-local.ps1 -SkipTests`) PASS; `tests/unit/architecture`, `tests/unit/modules/trading` and `tests/integration/application` 2475 passed. `tests/integration/presentation` has one failure, `test_workbench_conformance[True-1024x700]` (a Backtest window-fit measure), which fails identically on the untouched base.
