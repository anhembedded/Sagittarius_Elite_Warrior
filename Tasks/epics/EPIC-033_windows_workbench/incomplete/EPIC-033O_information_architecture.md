# EPIC-033O — The information architecture is designed from the use cases, with a wireframe per mode, and approved by the user

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI).
**Risk:** 🟢 — design only; it decides what every later task builds
**Complexity:** M — six modes, menus, commands and their wireframes
**Epic:** [EPIC-033](../README.md)
**Depends on:** EPIC-033A

---

## 1. Context and problem
Today's screens grew one feature at a time: three places to watch the market, two desks plus a dialog to place an order, a Welcome page, a Settings route, a Dev Board that holds a bit of everything. Rebuilding them one by one would carry that shape into the new UI. The design starts from what a person does (`Docs/SPEC/`, `Docs/PROJECT_INTENT_AND_USER_STORIES.md`) and from the desktop guidance in the rule (033A). A first draft is in the [UI review](https://claude.ai/artifact/Np92LCSrk2t2e8NQxLEkaE) §"Kiến trúc thông tin mới".

## 2. Acceptance criteria
- [ ] `Docs/HLD/11_desktop_workbench.md` holds the information architecture: the modes (draft: Market, Trade, Strategies, Backtest, Data, Developer), each with its purpose, its SPECs, its central widget, its panels and its default layout.
- [ ] The full menu bar with every command, its menu, access key, shortcut, ellipsis, toolbar placement and confirmation flag; no command reachable only by a shortcut or a context menu.
- [ ] What is always visible (Emergency Stop, the venue in text) and why.
- [ ] A wireframe per mode at 1366×768 and 1024×700, published for review; the user approves the set, and the approval is quoted in the epic's decision record.
- [ ] Every SPEC is placed in exactly one mode; every existing screen is mapped to the mode that replaces it or recorded as dropped with its reason.

## 3. Design
Task-first information architecture (KDE: "simple by default, powerful when needed"; MS: "focus on what is likely"): one mode per job the person does, the panels that job needs, the rest one menu away.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/HLD/11_desktop_workbench.md` | §11.2 rewritten as the information architecture |
| `Docs/VOCABULARY/README.md` | The mode names |
| `Tasks/epics/EPIC-033_windows_workbench/DECISION_2026-10-04_windows_workbench.md` | The user's approval |

## 5. Testing
Documentation-only: reference check and document guards. Approval is the user's.

## Implementation notes (written when done)
Not started.
