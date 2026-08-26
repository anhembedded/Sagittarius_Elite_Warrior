# EPIC-010 — Remembering the user's last values (UI State Persistence)

**Status:** 🔵 **Not started — awaiting design approval** (0/8 sub-tasks)
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

## The design

📄 **[`design/DESIGN_2026-08-25_ui_state_persistence.md`](design/DESIGN_2026-08-25_ui_state_persistence.md)**

That document contains: the structural model plus a 12-failure-mode catalogue
derived from the lifecycle of one persisted value, an evaluation of 7 design
decisions (each with an options table and the reasoning behind the choice), the
proposed architecture, and 12 mermaid diagrams (component, class, 2 sequence,
state machine, ER, 2 flowchart, mindmap, gantt, journey).

### The three decisions that matter most

| # | Decision | What decided it |
| :-: | :--- | :--- |
| **D1** | A **separate** `state/ui_state.json`, but backed by a **second `ConfigManager` instance** — not a hand-written store, not `QSettings` | The **file** must be separate because `user_config.json` is git-tracked **and** holds `API_KEY`/`API_SECRET`, and the Sanity tier loads that very file with `writable=True`. But the **mechanism** must not be: keep exactly one paradigm project-wide. A measured probe shows `ConfigManager` already provides slice-merge (D2) and fail-safe corruption handling — the two heaviest parts, free |
| **D2** | The document is split into **per-screen slices**; each write **merges one slice** and never replaces the whole document | `PresenterManager` is *TRUE LAZY* — a presenter is only built when the user visits that screen. Writing the whole document at shutdown would **wipe out** the slices for screens this session never opened |
| **D6** | Persist **intent**, never persist **activity** (FSM state, a running stream) | `BOT-062` deliberately disabled autostart because *"opening the Dev Board must not silently start a live connection unless the user has opted in"*. Restoring the FSM into `LIVE` routes around that exact decision through the back door |

## Sub-tasks (files not created yet — awaiting design approval)

| ID | Name | Tier | Status |
| :--- | :--- | :---: | :---: |
| `EPIC-010A` | `IUiStateStore` + `ConfigManagerUiStateStore` + unit tests for all 12 failure modes | Foundation | 🔵 Not started |
| `EPIC-010B` | `UiStateService` — debounce, flush inside `teardown()` | Foundation | 🔵 Not started |
| `EPIC-010C` | Shell: window size + last route + sidebar | T1 | 🔵 Not started |
| `EPIC-010D` | Dev Board: symbol + interval | T1 | 🔵 Not started |
| `EPIC-010E` | Database: symbol + interval | T1 | 🔵 Not started |
| `EPIC-010F` | Backtest: the full slice | T2 | 🔵 Not started |
| `EPIC-010G` | Indicator scripts + the `_user_touched` flag | T2 | 🔵 Not started |
| `EPIC-010H` | Collapse duplicated defaults into one source | Tech debt | 🔵 Not started |

> Sub-task files are **deliberately not created yet**. The design still has 3 open
> questions for the user (see §8 of the design doc), and writing 8 task files for
> an unapproved design is exactly the "guessing the shape of something that does
> not exist yet" mistake that `architecture-rule.md` §7.2 names as the lesson from
> `EPIC-006`'s four stub cards.

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
