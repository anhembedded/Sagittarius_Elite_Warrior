# EPIC-033 — The app is one Windows workbench of stock controls

- **Status:** 🟡 In progress
- **Repositories:** both — the app here; the workbench mechanism in `Sagittarius_Engine` (Engine track below, tracked on the Engine's own board)
- **Origin:** the user, 2026-10-04, after the [UI review](https://claude.ai/artifact/Np92LCSrk2t2e8NQxLEkaE): "tui thấy nó khó dùng quá, ko đúng triết lý Window app thì phải, các layer tào lau quá. các nút thì quá bự, tự resize kém, các menu thì ko có continer ẩn hiện gì cả, chiếm hết diện tích" (it is too hard to use, not the Windows-app philosophy; the layers are a mess; the buttons are too big; it resizes badly; the panels have no container to show or hide, they take all the space); "plan của epic phải sữa triệt đễ từ mặt triết lý tới cơ chế, ko hot fix, cái nào cần sử bên engien thì sửa bên engine" (the epic's plan must fix things at the root, from philosophy to mechanism, no hotfix; what needs changing in the engine is changed in the engine); "các UI thì phải đồng nhất, cũng là button sao mà nhiều kiểu quá, 1 kiểu thui, ra soát lại hết, khong có cái nào khác lại, hay làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform; why are there so many kinds of button — one kind only; review everything, nothing different; build a plain UI first, but true to the Windows-app philosophy; design comes later).
- **North star:** `Docs/HLD/11_desktop_workbench.md` (the workbench) and `.claude/rules/ui-presentation-rule.md` (the stock-control contract, rewritten by 033A)
- **Decisions:** [DECISION_2026-10-04_windows_workbench.md](DECISION_2026-10-04_windows_workbench.md)
- **Dependencies:** the Engine track W1-W6 (released in Engine 3.0.0, pinned by the app's `engine.ref` in PR #337); EPIC-025's surfaces and contribution registry. Phase 2 first waited for EPIC-029 (the user, 2026-10-04: "P4 của EPIC-033 chưa làm dc, chờ epic 29 đã"), then the user lifted the wait the same day: "còn test của epic 29 thì từ từ test, cứ làm epic 33 đi" (EPIC-029's testing can take its time; go ahead with EPIC-033)

---

## 1. Decisions already made
1. D1 — one look per control kind: stock Qt widgets with their defaults, the platform style, no per-widget style, palette, font or size; visual design is deferred.
2. D2 — every fix lands at its mechanism; a rule without a check is not done.
3. D3 — the generic workbench mechanism is built in the Engine now, directly, not harvested from the app later (the user confirmed, superseding TASK-043's harvest-first rule for this mechanism).
4. D9 — display widgets are uniform too: every table, list and read-out of the same kind has the same properties, declared once per column or value kind, never set per view.
5. D10 — the UI is redesigned from the use cases, not rebuilt screen by screen: EPIC-033O designs the modes (Market, Trade, Bots, Backtest, Data, Developer) and the user approves them before any mode is built.
6. D11 — the rule is the desktop guidance of Microsoft, KDE and Apple (cited per clause); where they disagree, the Windows desktop choice wins (Tools → Options, platform button order through `QDialogButtonBox`).
7. D4-D8 — shell, chart, font, superseded guards, dark mode: see the decision record.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-04, 1366×768) | When the epic is done |
| :--- | :-: | :-: |
| Menu-bar actions | 0 | File, Edit, View, Window, Help; every command reachable |
| Modes that are workbenches (docks, View, perspective) | 1 of 8 | all |
| Distinct button looks (review inventory) | 13 | 1 (the platform's `QPushButton`, `QToolButton` on toolbars) |
| `setStyleSheet` / `apply_role` calls in `src` | 133 / 40 | 0 / 0 |
| Fixed or minimum control sizes in `src` | 36 | 0 |
| Widgets with a style sheet on one screen (max) | 90 | 0 |
| Controls taller than their own size hint (max per screen) | 20 | 0 |
| Scroll areas nested inside scroll areas (max depth) | 2 | 0 |
| Commands that are `QAction`s | 8 | every command |
| Perspectives saved and restored | 0 | every mode |
| Log consoles | 4 cards | 1 Output dock |
| Item views configured outside one spec | 12 of 12 (selection set on 8, edit triggers on 4, `setSectionResizeMode` 26 ad-hoc calls) | 0: every view built from a column spec |
| Value formatters written per screen (`_format_price`, `_format_datetime`, `_format_compact_usd`, …) | ≥ 8 | 0: one formatter per value kind |
| `kit/` files | 29 | 0 |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-033A](incomplete/EPIC-033A_stock_control_contract.md) | The UI rule is the desktop guidance of Microsoft, KDE and Apple, written as checkable clauses | Elite | None | 🟢 | 🟡 In progress (merged in PR #332; open criteria listed in the task) |
| [EPIC-033O](completed/EPIC-033O_information_architecture.md) | The information architecture is designed from the use cases, with a wireframe per mode, and approved by the user | Elite | EPIC-033A | 🟢 | ✅ Done (2026-10-04) |
| [EPIC-033B](incomplete/EPIC-033B_workbench_conformance_fences.md) | A booted-app conformance suite and static bans hold the contract, shrink-only until each mode migrates | Elite | EPIC-033A, EPIC-033O | 🟡 | 🟡 In progress (merged in PR #332; open criteria listed in the task) |
| [EPIC-033C](incomplete/EPIC-033C_workbench_shell.md) | One top-level workbench window: menu bar, mode bar, View menu, Reset layout, status bar | Elite | Engine W1, EPIC-W3; 033B | 🔴 | 🟡 Merged (#345); two conformance checks still owed, listed in the task |
| [EPIC-033D](completed/EPIC-033D_commands_as_actions.md) | Every command is one QAction contributed by its module: menu entry, toolbar button and shortcut share it | Elite | Engine W2; 033C | 🟡 | ✅ Done (2026-10-05) |
| [EPIC-033N](incomplete/EPIC-033N_uniform_display_widgets.md) | Every table, list and read-out is built from one spec per kind | Elite | Engine W6, EPIC-033C | 🟡 | In progress (tables done) |
| [EPIC-033E](completed/EPIC-033E_settings_dialog.md) | One Options dialog (Tools → Options) with sections, OK, Cancel and Apply | Elite | Engine W4; 033C | 🟡 | ✅ Done (2026-10-04) |
| [EPIC-033F](completed/EPIC-033F_one_output_dock.md) | One Output dock with a channel per module replaces three log cards | Elite | Engine W4; 033C | 🟢 | ✅ Done (2026-10-04) |
| [EPIC-033G](completed/EPIC-033G_stock_chart_controls.md) | The chart is a canvas; its controls are actions in the toolbar and the context menu | Elite | EPIC-033D | 🟡 | ✅ Done (2026-10-05) |
| [EPIC-033H](completed/EPIC-033H_market_mode.md) | Market mode: watch the market, laid out as HLD §11.2.1 designs it | Elite | EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N | 🟢 | ✅ Done (2026-10-05) |
| [EPIC-033I](incomplete/EPIC-033I_trade_mode.md) | Trade mode: one mode for both venues, laid out as HLD §11.2.1 designs it | Elite | EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N | 🔴 | Planned |
| [EPIC-033J](incomplete/EPIC-033J_data_mode.md) | Data mode: keep history complete, laid out as HLD §11.2.1 designs it | Elite | EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N | 🟡 | Planned |
| [EPIC-033K](incomplete/EPIC-033K_bots_mode.md) | Bots mode: create, judge, run and watch bots, laid out as HLD §11.2.1 designs it | Elite | EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N | 🔴 | Planned |
| [EPIC-033L](incomplete/EPIC-033L_backtest_mode.md) | Backtest mode: test a strategy on stored history, laid out as HLD §11.2.1 designs it | Elite | EPIC-033O (approved design of this mode), EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G, EPIC-033N | 🟡 | Planned |
| [EPIC-033P](incomplete/EPIC-033P_developer_mode.md) | Developer mode: the testbed, only when developer mode is on | Elite | EPIC-033O, EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G | 🟢 | Planned |
| [EPIC-033M](incomplete/EPIC-033M_retire_kit.md) | The kit, the palette and the theme bootstrap are deleted; every ratchet becomes a ban | Elite | EPIC-033H, EPIC-033I, EPIC-033J, EPIC-033K, EPIC-033L, EPIC-033N, EPIC-033P | 🟢 | Planned |

### Engine track (Sagittarius_Engine, its own board; listed here as dependencies only, ONBOARDING §9)
The Engine epic is scaffolded in that repository by its own rules (`.agents/rules/task-tracking.md`), starting with the PlantUML as-is / to-be diagrams its onboarding §10.5 asks for before any task file.
| Id | Mechanism | Replaces / extends |
| :--- | :--- | :--- |
| W1 | `RegionHost`: toolbars take `QAction`s and are movable; a public `dock_toggle_actions()`; named, versioned perspectives persisted through `ui_state` | `region_host.py` (`addWidget` toolbars, private `_docks`, one perspective blob) |
| W2 | `ActionDescriptor` contributions: id, text, icon, menu path, toolbar, shortcut, enabled/checked binding, `confirm` flag; duplicate ids and shortcuts refused | none today |
| W3 | `WorkbenchShell`: top-level window with the standard menu bar, a mode bar (`QActionGroup`), the mode stack, View built from the current mode's docks, Window → Reset layout, status bar; `NavigationService` with `source` and `can_leave` (TASK-043 E3) | `PresenterManager`'s bare stack |
| W4 | `SettingsDialog` host (page contract: apply, revert, dirty; `QDialogButtonBox`) and an `OutputPane` dock with contributed channels | none today |
| W6 | Display conventions: `ColumnSpec`/`ColumnKind` (text, quantity, price, percent, money, timestamp, side, status) deciding alignment, width policy, sort role and formatting; one `configure_item_view()` for selection, edit triggers, header and sorting; a `ReadoutForm` for label–value pairs; a `ValueFormatter` port the app implements with its precision policy | 12 item views configured by hand; ≥ 8 per-screen formatters |
| W5 | `.agents/rules/ui-architecture.md` rewritten for QtWidgets and the platform style; the tokens and QML kit scoped to QML consumers; the `widgets/` documentation drift fixed | rule §1-§2 (tokens own every colour and size) |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 0 — Contract and fences | 033A + 033B merged; every violation measured into a shrink-only baseline | Conformance suite green with its baseline; mutation runs recorded |
| 1 — Engine mechanism | W1-W6 released in an Engine version the app pins in `engine.ref` | Engine gate; the app's shell builds on it |
| 0b — Design | 033O approved by the user | The user's approval quoted in the decision record |
| 2 — Shell | 033C-033G and 033N merged; shell checks removed from the baseline for every mode | Conformance suite; desktop E2E layout round-trip |
| 3 — Modes | 033H-033L and 033P merged; each mode's baseline rows gone | Conformance suite per mode; Testnet confirmation by the user for 033I and 033K |
| 4 — Retire | 033M merged; every baseline empty, every ratchet a ban | Full gate |

## 5. Out of scope
Visual design (colours, icon set, branding, a designed dark theme) — deferred by the user (D1); dark mode comes only from the operating system's colour scheme (D8). The Bots tab (`EPIC-029F`, PR #333) is born a workbench host: a `WorkbenchSurface` (the Engine's `RegionHost`) with stock controls and no style sheet, so it passes every conformance check. Its 7 per-view item-view calls wait in `baseline_stock_controls.json` for `EPIC-033N`; `EPIC-033K` re-lays it out on `WorkbenchShell`. Engine-side retirement of the QML kit is the Engine's own decision (W5 only scopes it).

## Notes (newest first)
- **2026-10-04** — Redesign from the use cases (D10) and the rule grounded in Microsoft/KDE/Apple guidance (D11): 033O and 033P added; the screen-by-screen tasks became mode tasks; Settings became Tools → Options.
- **2026-10-04** — The user confirmed D3 (engine directly) and added D9 (uniform display widgets): W6 and 033N added.
- **2026-10-04** — Epic planned from the UI review and three user messages; nothing implemented.
