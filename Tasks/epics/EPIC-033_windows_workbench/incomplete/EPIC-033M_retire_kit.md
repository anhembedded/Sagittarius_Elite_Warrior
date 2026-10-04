# EPIC-033M — The kit, the palette and the theme bootstrap are deleted; every ratchet becomes a ban

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟢 — a shared surface changes shape
**Complexity:** M — deletion
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033H, EPIC-033I, EPIC-033J, EPIC-033K, EPIC-033L, EPIC-033N, EPIC-033P

---

## 1. Context and problem
HLD §11.4 makes deleting `Palette`, `kit/style.py` and `seed_app_theme()` the last step, once nothing reads them; `kit/` is 29 files (~4,578 lines) with 47 importers in `src`.

## 2. Acceptance criteria
- [ ] `src/support/ui_kit/kit/`, `palette.py`, `theme_bootstrap.py`, `PageShell`, `StyledButton`, the sidebar and every replaced screen are deleted; `configure_app_qml` and `get_theme_bridge` are no longer called.
- [ ] `baseline_stock_controls.json`, `baseline_workbench_conformance.json` and `baseline_app_styling.json` are empty and their guards become bans.
- [ ] HLD §11.4's last row is marked done with the commit.

## 3. Design
Strangler Fig's last step (HLD §6.3).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/ui_kit/` | Deleted parts |
| `tests/unit/architecture/test_app_styling_only_shrinks.py` | Becomes a ban |

## 5. Testing
Full gate; conformance suite with an empty baseline.

## Implementation notes (written when done)
Not started.
