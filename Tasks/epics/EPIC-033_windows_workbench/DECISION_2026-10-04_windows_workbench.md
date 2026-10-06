# ADR — The app is one Windows workbench of stock controls, built on Engine workbench mechanism

**Epic:** [EPIC-033](README.md)
**Date:** 2026-10-04
**Status:** Accepted
**Decided by:** the user for D1-D3, D9-D11; the agent under ONBOARDING §7 and CONSTITUTION P5/P6 for D4-D8

## 1. Context
The [UI review](https://claude.ai/artifact/Np92LCSrk2t2e8NQxLEkaE) ran the real app at 1024×700, 1366×768 and 1920×1080 and measured: no menu bar; 1 of 8 modes a workbench; three visual systems at once (the `kit` dark theme, stock widgets, the black pyqtgraph canvas); up to 90 styled widgets and 20 oversized controls per screen; scroll areas two deep; six 32 px buttons placed over the chart; labels whose `&` became a mnemonic. The causes are mechanisms, not screens: a per-widget QSS builder (`kit/style.py`), fixed heights written per widget, overlay widgets positioned by `move()`, a shell without a menu bar, an Engine region host whose toolbars take widgets and whose docks are private, and guards that reward the `kit` look. HLD §11 already chose the workbench; nothing enforced it.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | One look per control kind: every control is a stock Qt class with its defaults in the platform style; no per-widget style sheet, palette, font or size; colour only where it carries meaning. Visual design comes later. | Accepted | 🟢 user: "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later) | Every `StyledButton`, card and custom size goes; the app looks plain and native until a design is chosen |
| D2 | Fix at the mechanism, from the philosophy down; a rule clause without a check is not done; no screen-level patch. | Accepted | 🟢 user: "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine) | 033A/033B come first; each mode's fix removes its baseline rows |
| D3 | The generic workbench mechanism (W1-W6) is built in the Engine now, directly; nothing is harvested from the app first. | Accepted | 🟢 user: "làm trực tiếp bên engine luôn, ko cần phải dựng ở app trước" (do it directly in the engine, no need to build it in the app first), and earlier "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" | Supersedes TASK-043's harvest-first rule for this mechanism. Buys one implementation of standard Qt shapes the Engine already half-owns (`RegionHost` is a `QMainWindow`); costs Engine API commitments before a second consumer exists, accepted for speed |
| D4 | Every mode is a workbench host in one top-level shell; a mode bar replaces the sidebar; the options are one dialog (D11: Tools → Options). | Accepted | 🤖 agent; HLD §11.2, Qt Creator | The sidebar and the settings route are deleted |
| D5 | The chart stays pyqtgraph; nothing is placed over the plot; its controls are actions; its neutral colours come from `QPalette`, its meaning colours from one named table. | Accepted | 🤖 agent; trading-terminal convention | `ZoomControls` is deleted |
| D6 | The application font is the platform's; a fixed-pitch system font only where digits align. | Accepted | 🤖 agent; Windows UX guidelines | `_apply_font` (Consolas 10 pt) is deleted |
| D7 | Guards that reward the `kit` look are superseded by checks that forbid strictly more, in the same commit (P8). | Accepted | 🤖 agent; CONSTITUTION P8 | `test_widget_guards_hold`, `test_app_owns_its_size_tokens`, `test_palette_is_the_only_color_source` are deleted by 033B |
| D9 | Display widgets are uniform: every table, list and read-out of a kind shares its properties, declared once per column or value kind (`ColumnSpec`, `ValueFormatter`, `ReadoutForm`), never configured per view. | Accepted | 🟢 user: "ko chỉ cần control thống nhất, mà các widget hiện thị cũng phải thống nhất, ví dụ mấy cái mảng thì phải thông nhất các properti" (not only the controls: the display widgets must be uniform too, e.g. the tables must share the same properties) | 12 item views and ≥ 8 per-screen formatters are rebuilt on one spec (033N, Engine W6) |
| D10 | The UI is redesigned from the use cases: modes, panels, menus and commands are designed in EPIC-033O and approved by the user before any is built; no screen is rebuilt for its own sake. | Accepted | 🟢 user: "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI) | Six draft modes (Market, Trade, Strategies, Backtest, Data, Developer); Welcome, the Settings route and the separate Watchlist, Futures and Spot screens are dropped |
| D11 | The UI rule is the desktop guidance of Microsoft (Windows UX Interaction Guidelines, Fluent), KDE, Apple and GNOME, cited per clause; where they disagree the Windows desktop choice wins: Tools → Options with OK/Cancel/Apply, platform button order via `QDialogButtonBox`, Windows capitalisation, Qt style metrics instead of any fixed grid. | Accepted | 🟢 user: "tốt nhất là nên tham khảo triết lý UI WINDOW của các tổ chức lớn" (best to draw on the Windows UI philosophy of the major organisations) | The rule changes wording from "Settings" to "Options"; `QKeySequence.Preferences` (empty on Windows) replaces Ctrl+, |
| D8 | Dark mode, if wanted, is the operating system's colour scheme, never an app theme. | Accepted | 🤖 agent; HLD §11.4 | No theme code returns |

## 3. Alternatives considered
- **Restyle the screens consistently** (one QSS for all buttons): keeps a theme layer HLD §11.4 already retired, and fixes the look, not the missing menus, docks and perspectives. Rejected (D2).
- **Harvest-first** (build the shell in the app, move it to the Engine after a second consumer): the recorded TASK-043 rule; it delays the Engine shapes and contradicts the user's instruction to fix the Engine where the mechanism lives. Rejected by the user in favour of D3.
- **QML**: rejected by ADR D20-D22.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| — | None open. O1 (engine-first) was answered by the user on 2026-10-04: D3 accepted. | — | — |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1, D2, D7 | EPIC-033A, EPIC-033B | Not started | Not yet verified |
| D3 | Engine track W1-W6 | Not started | Not yet verified |
| D9 | Engine W6, EPIC-033N | Not started | Not yet verified |
| D10 | EPIC-033O, then 033H-033L, 033P | Design approved; modes not built | User, 2026-10-04: "approve", on the wireframes (https://claude.ai/artifact/SpmngbczYacm9UwrrXYHbd) and HLD §11.2 as merged in PR #332; after approval the user pointed at the Bots tab (PR #333): "you check EPIC-029 doc, there are decision for this question, just follow" — the Strategies mode became Bots, per EPIC-029's own decisions |
| D11 | EPIC-033A, Engine EPIC-008A | Not started | Not yet verified |
| D4 | EPIC-033C, EPIC-033E | Not started | Not yet verified |
| D5 | EPIC-033G | Not started | Not yet verified |
| D6 | EPIC-033C (application font), EPIC-033N (fixed-pitch font where digits align) | Application font done | Conformance `system_font` check (`_apply_font` deleted); the fixed-pitch half is open in EPIC-033N |
| D8 | EPIC-033M | Not started | Not yet verified |
