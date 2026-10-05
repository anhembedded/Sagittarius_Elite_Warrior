# BOT-152 — The order entry's view model splits what the presenter sets from what the view asks

**Status:** 🔵 Backlog
**Source:** the review of PR #358 (EPIC-033R), 2026-10-05: `OrderEntryViewModel` grew to 30 public members, already over `PLR0904`'s 20, and the ratchet counts files, not members, so growth inside the file is invisible to it.
**Risk:** 🟢 — a split along a line the class already draws in its section comments
**Complexity:** S
**Epic:** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md) (the desks become the Trade mode in `EPIC-033I`)
**Depends on:** —

---

## 1. Context and problem
`src/modules/trading/ui/desk/order_entry/order_entry_view_model.py` holds three kinds of member under one class: reads (`entry`, `figures`, `can_take_order`, …), the user's intents (`set_price`, `request_submit`, `request_focus`, …) and the presenter's writes (`begin_symbol`, `set_context`, `show_result`, …). It is one `PLR0904` entry in `baseline_ruff_debt.json`, so adding a member does not move the ratchet.

## 2. Acceptance criteria
- [ ] No class in the order entry's view model has more than 15 public methods (`architecture-rule.md` §5.4).
- [ ] Its `PLR0904` entry leaves `baseline_ruff_debt.json`.
- [ ] Every test of the order panel, its presenter and the desks passes unchanged in what it asserts.

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
Not started.
