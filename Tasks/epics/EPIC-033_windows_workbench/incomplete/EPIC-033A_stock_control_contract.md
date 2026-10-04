# EPIC-033A — The UI rule is the desktop guidance of Microsoft, KDE and Apple, written as checkable clauses

**Status:** 🟡 In progress (merged in PR #332; open criteria listed in the task)
**Source:** the user, 2026-10-04 — "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); then "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); then "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
**Risk:** 🟢 — a shared surface changes shape
**Complexity:** S — documents only
**Epic:** [EPIC-033](../README.md)
**Depends on:** None

---

## 1. Context and problem
`ui-presentation-rule.md` §1 already says "QtWidgets only, OS theme", yet the tree carries 133 `setStyleSheet` calls, 40 `apply_role` calls, 21 `StyledButton`s and 36 fixed control heights, and three of its own guards push new widgets toward the `kit` look (`test_widget_guards_hold.py` caps bare Qt bases at 2, `test_app_owns_its_size_tokens.py` locks pixel sizes, `test_palette_is_the_only_color_source.py`). The rule names no contract a machine can check, so the tree drifted three ways at once ([review](https://claude.ai/artifact/Np92LCSrk2t2e8NQxLEkaE), UX-01..UX-11).

## 2. Acceptance criteria
- [x] The rule's principles and clauses cite their source: Microsoft Windows User Experience Interaction Guidelines (`learn.microsoft.com/windows/win32/uxguide`), Microsoft Fluent / Windows app design, KDE HIG (`develop.kde.org/hig`), Apple HIG, GNOME HIG and Qt's styling guidance, read 2026-10-04 and digested in the [UI review](https://claude.ai/artifact/Np92LCSrk2t2e8NQxLEkaE) §"Triết lý UI desktop"; the user asked for this: "tốt nhất là nên tham khảo triết lý UI WINDOW của các tổ chức lớn" (best to draw on the Windows UI philosophy of the major organisations).
- [x] The clauses cover menus (order File, Edit, View, Tools, Window, Help; access keys on every item, unique per menu; "…" (U+2026) exactly on commands needing more input; disable, never hide), toolbars (every toolbar command also in a menu; tooltips with shortcuts), buttons (one style, no fixed size, no checkable push buttons), dialogs (`QDialogButtonBox` only; one safe default; Esc closes; Apply only while changes are pending; title names the command), layout and fonts (style metrics, system font), colour (no RGB literals, no colour-only meaning, High Contrast usable), panels (unique object names, View toggles, saved layout), tables (numbers right-aligned, full-row selection, sortable, movable and remembered columns, an empty state that instructs), feedback (progress after 2 s, Stop vs Cancel, status bar never the only alarm), confirmations (risky actions only, safe default, specific verbs) and keyboard (standard shortcuts kept, allowed set for new ones, reading-order tabs).
- [x] Where the sources disagree (button order, Options vs Settings, apply timing, capitalisation, spacing system), the rule records the choice: platform order through `QDialogButtonBox`; Tools → Options; OK/Cancel/Apply; Windows capitalisation; the Qt style's metrics.
- [x] `DECISION_2026-10-04_windows_workbench.md` D1-D8 are recorded with the user's words.
- [x] `ui-presentation-rule.md` states the stock-control contract: every control is a stock Qt class constructed with its defaults; no per-widget style sheet, palette, font or size; colour only where it carries meaning, through `QPalette` roles; every command is a `QAction`; every mode is a workbench; one Settings dialog; one Output dock; every table, list and read-out is built from its kind's spec (D9), with values formatted by kind, never per screen.
- [ ] Every clause of the contract carries a `[guard: …]` tag naming the 033B check that enforces it; the rule checker resolves them. — the clauses a booted window or a line of code can show carry `[guard: …]`; wording, tab order and confirmation text carry `[review: H3]`/`[review: H7]`, since no check sees them.
- [x] HLD §11.4 and §11.5 cite the contract and drop the claim "enforced" from any rule no check enforces.

## 3. Design
The contract is written as checkable predicates, not adjectives (P1, P11). It cites HLD §11 for the reasons and adds only what the review proved missing: one look per control kind, no custom size, no nested scroll, no overlay widget on a canvas, labels escape `&`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Tasks/epics/EPIC-033_windows_workbench/DECISION_2026-10-04_windows_workbench.md` | The decisions |
| `.claude/rules/ui-presentation-rule.md` | §1-§3 rewritten as the stock-control contract, each clause tagged |
| `Docs/HLD/11_desktop_workbench.md` | §11.4/§11.5 cite the contract; unenforced claims corrected |
| `Docs/VOCABULARY/README.md` | "workbench", "mode", "mode bar", "perspective", "Output channel", "stock control" |

## 5. Testing
Documentation-only: `python3 scripts/check_skill_prompt_references.py` and the document guards. The tags resolve only once 033B's checks exist, so 033A lands in the same pull request as 033B.

## Implementation notes (written when done)
- `ui-presentation-rule.md` rewritten: §1 stock controls in the platform's look, §2 principles (with their sources), §3 layout, §4 text and icons, §5 preview kept as anchors; new §6 menus and commands, §7 dialogs and Options, §8 panels and perspectives, §9 tables and read-outs, §10 feedback and confirmations, §11 keyboard. Sources named once at the top; the dated reading lives in the decision record (the rule checker bans dates in rules).
- The principle "the UI thread never blocks", cited from `monte_carlo_coordinator.py`, is kept as the "Responsive" row.
- HLD §11 header and §11.5 now cite the rule and name the check behind each enforced claim; §11.4 is unchanged (its ratchet is still true).
- Open: D1-D8 user quotes are in the decision record; this task's last box closes with the PR's review.
