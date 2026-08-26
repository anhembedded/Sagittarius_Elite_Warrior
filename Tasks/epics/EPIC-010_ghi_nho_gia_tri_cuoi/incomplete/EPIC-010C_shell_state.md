# EPIC-010C — Shell: window geometry, splitters, last route, sidebar

**Status:** 🔵 Not started
**Repo:** **Elite** (`Sagittarius_Elite_Warrior`) — design §8 step 3
**Depends on:** `EPIC-010B`

## What

The first real consumer. A `ShellStateContributor` on `MainWindow`, scope
`StateScope("shell", None, PERSISTENT)`, holding four things — and **three of
them are Qt blobs, not hand-written fields**:

| Value | Source | Hand-written? |
| :--- | :--- | :---: |
| Window size / position / maximised | `QWidget.saveGeometry()` → base64 | ❌ Qt |
| Splitter positions | `QSplitter.saveState()` → base64 | ❌ Qt |
| Table column widths, where present | `QHeaderView.saveState()` → base64 | ❌ Qt |
| Last open route | `MainWindow.switch_screen`'s argument | ✅ one string |
| Sidebar collapsed | `SidebarViewModel._is_collapsed` | ✅ one bool |

Base64 via `QByteArray.toBase64()`/`fromBase64()` — measured to round-trip
exactly (design §5.6.6 row 10).

## Why the blobs, not x/y/w/h

Design §5.6.3 corrects the first design's §4.1.2: `restoreGeometry()` already
performs its own off-screen and DPI sanity checks, so hand-rolled coordinates
buy nothing and get multi-monitor wrong in ways Qt handles. **Let Qt own what Qt
owns.**

This also pulls splitter sizes out of the deferred **T3** tier — they were
deferred because `dashboard_view.py:59-61` re-applies `[900, 400]` on every
construction, but `QSplitter.saveState()` sidesteps that entirely.

## Restore is still a request (D5)

- Last route: only navigate there if it is still registered with
  `PresenterManager`; otherwise fall back to `"dashboard"`.
- `restoreGeometry()` returning `False` is not an error — use the default size.

## Acceptance

- Resize, move, switch to Backtest, collapse the sidebar, quit, relaunch →
  all four come back
- A route that no longer exists in the state file → boots to `dashboard`, no error
- A corrupt `ui_state.json` → boots at default size, cleanly (the Sanity tier's
  `diagnostic_guard` already fails on any complaint)
- Boot performs **no** navigation side effects beyond the one restore
