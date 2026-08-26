# EPIC-010 — Remembering the user's last values (UI State Persistence)

**Status:** 🟢 **Design closed 2026-08-26** — 0/5 first-pass sub-tasks built; 3 more held pending evaluation
**Created:** 2026-08-25

---

## The problem

The app has exactly **one** path that writes to disk: the Settings screen saves 5
keys (`API_KEY`, `API_SECRET`, `DEFAULT_SYMBOLS`, `DEFAULT_INTERVAL`,
`DEFAULT_SYNC_DAYS`) into `src/config/user_config.json`.

**Everything else the user touches is lost when the app closes** — roughly **45
values** across 4 screens: the Dev Board's symbol and interval, the entire
Backtest form (strategy, capital, timeframe, date range, commission, leverage…),
the Database screen's selections, window size, which screen was open, and which
indicator scripts were enabled.

A repo-wide grep confirms it: **no `QSettings`**, **no
`saveGeometry`/`restoreGeometry`**, and **no `config.set()`** anywhere in
`src/presentation/` outside `settings_presenter.py`.

## The design — read both, in this order

1. 📄 **[`design/DESIGN_2026-08-25_ui_state_persistence.md`](design/DESIGN_2026-08-25_ui_state_persistence.md)**
   — the problem, the scope, failure modes 1-12, and decisions D2/D4/D5/D6/D7.
   12 mermaid diagrams. **D1's location and D3 are superseded by (2).**
2. 📄 **[`design/DESIGN_2026-08-26_engine_state_extension.md`](design/DESIGN_2026-08-26_engine_state_extension.md)**
   — moves the mechanism into the Engine as `UiStateExtension`, and replaces
   route-keyed slices with `StateScope` (key + instance + lifetime), so any
   form of multiplicity — tabs, a second window, split panes — has an identity.
   Adds failure modes 13-16, the reuse audit (§5.6.6), and §9.1's settled
   product decisions.

The second document exists because review found a real hole in the first: it
keyed every slice by **route name**, which silently assumes one presenter per
route. Four copies of the same view would have collapsed into one shared slice
— and the same defect applies to the `shell` slice the moment a second window
can exist.

### The three decisions that matter most

| # | Decision | What decided it |
| :-: | :--- | :--- |
| **D1** | A **separate** `state/ui_state.json`, but backed by a **second `ConfigManager` instance** — not a hand-written store, not `QSettings` | The **file** must be separate because `user_config.json` is git-tracked **and** holds `API_KEY`/`API_SECRET`, and the Sanity tier loads that very file with `writable=True`. But the **mechanism** must not be: keep exactly one paradigm project-wide. A measured probe shows `ConfigManager` already provides slice-merge (D2) and fail-safe corruption handling — the two heaviest parts, free |
| **D2** | The document is split into **per-screen slices**; each write **merges one slice** and never replaces the whole document | `PresenterManager` is *TRUE LAZY* — a presenter is only built when the user visits that screen. Writing the whole document at shutdown would **wipe out** the slices for screens this session never opened |
| **D6** | Persist **intent**, never persist **activity** (FSM state, a running stream) | `BOT-062` deliberately disabled autostart because *"opening the Dev Board must not silently start a live connection unless the user has opted in"*. Restoring the FSM into `LIVE` routes around that exact decision through the back door |
| **D8** | The mechanism lives in the **Engine**; the key carries **identity and lifetime** from day one, but no tab machinery is built | `PresenterManager` holds exactly one presenter instance per route today, so tabs are structurally impossible — building for them now would be speculation. But adding identity to a key *later* is a data migration plus a breaking API change across two repos, while adding it *now* is one optional field. Asymmetric cost, so the shape goes in early and the machinery does not |

## Sub-tasks

**Design closed 2026-08-26.** The three product decisions are settled (see the
engine design doc §9.1): first-pass scope, dates as a **duration**, and
`state/ui_state.json` in the repo.

### First pass — build these, then stop and run it for real

> ✅ **Xong 2026-08-26 (PR #109).** `010A`/`010B` dựng trong **Elite**, chưa
> promote lên Engine — theo đúng quyết định "Elite first". Cột Repo dưới đây
> ghi nơi code **đang** nằm, không phải nơi nó sẽ về.
>
> Một việc không có trong bảng nhưng bắt buộc phải làm: **wire coordinator vào
> composition root**. Không có nó thì `010A`–`010C` chỉ sống trong test và
> **chết trong app thật**.

| ID | Name | Repo | Status |
| :--- | :--- | :---: | :---: |
| **[`EPIC-010A`](incomplete/EPIC-010A_state_scope_and_store.md)** | `StateScope`, `IStateStore`, the ConfigManager-backed store | Elite | ✅ Done 2026-08-26 |
| **[`EPIC-010B`](incomplete/EPIC-010B_coordinator_and_contributor.md)** | `UiStateCoordinator`, contributor contract, `UiStateExtension` | Elite | ✅ Done 2026-08-26 |
| **[`EPIC-010C`](incomplete/EPIC-010C_shell_state.md)** | Shell — geometry, splitters, last route, sidebar | Elite | ✅ Done 2026-08-26 |
| **[`EPIC-010D`](incomplete/EPIC-010D_dev_board_state.md)** | Dev Board — symbol, interval, lookback duration | Elite | ✅ Done 2026-08-26 |
| **[`EPIC-010E`](incomplete/EPIC-010E_database_state.md)** | Database — symbol, interval | Elite | ✅ Done 2026-08-26 |

### Held until the first pass has run

| ID | Name | Why it waits |
| :--- | :--- | :--- |
| **[`EPIC-010F`](incomplete/EPIC-010F_backtest_state.md)** | Backtest — 19 form values | ✅ **Done 2026-08-26.** 58 Property → 19 giá trị là *ý định*; phần còn lại là output hoặc trạng thái phiên. `selectedSymbol`/`selectedTimeframe` cố ý **không** lưu — chúng là chỗ duy nhất đụng thứ tự ưu tiên 3 tầng, thuộc `010H` |
| **[`EPIC-010G`](incomplete/EPIC-010G_indicator_scripts.md)** | Indicator scripts + the `_user_touched` flag | ✅ **Done 2026-08-26.** Lưu **2** tập (`enabled` + `touched`) — chỉ nhớ tập bật là không đủ. `restore_selection()` **lớp lên** default chứ không thay thế, để script `default_enabled` mới thêm vẫn tự bật cho user đã có slice |
| **[`EPIC-010H`](incomplete/EPIC-010H_defaults_precedence.md)** | Thứ tự ưu tiên 3 tầng + dẹp default trùng | 🟡 **Precedence xong 2026-08-26** (`discard_keys()` + Settings vô hiệu đúng 2 key nó sở hữu; mở khoá 2 field cuối của `010F`). **Dẹp literal trùng vẫn còn** — tách vì đó là thay đổi hành vi, không phải dọn dẹp |

> Task files for `010F`–`010H` are not written yet, on purpose. Their shape
> depends on what the first pass teaches, and writing them now would be the
> "guessing the shape of something that does not exist yet" mistake
> `architecture-rule.md` §7.2 names as the lesson from `EPIC-006`'s four stub
> cards.

## `EPIC-010H` is not a side quest

The same concept currently has several independent copies: `"ETHUSDT"` is a
literal in **3 files**, `"1m"` in **4+**. And only `BackTestPresenter` reads
`DEFAULT_SYMBOLS`/`DEFAULT_INTERVAL` from config — the Dev Board and Database
screens ignore them entirely, so **changing Settings today already produces
inconsistent defaults across screens**.

Stacking a "last value" tier on top of that foundation creates a three-level
precedence order nobody has defined. §7 of the design doc proposes:

```text
ui_state (what the user just did)  >  user_config DEFAULT_* (what they declared in Settings)  >  module constants
```

with one mandatory consequence: **changing a value in Settings must delete the
corresponding key from `ui_state`** — otherwise the user changes Settings and
sees nothing happen.

## Related

- [`BOT-115`](../../backlog/BOT-115_backtest_report_persistence_epic.md) —
  persisting **backtest reports** to a file. A different epic (it stores *the
  result of one run*, not *the user's selections*), but it already settled two
  principles this one reuses: JSON with a `schema_version`, and **never
  `pickle`**.
- [`BOT-047`](../../completed/BOT-047_dynamic_params_form_ui.md) — has a "Khôi
  phục Mặc định" (Restore Defaults) button; the UI precedent for R1 in the design
  doc.
