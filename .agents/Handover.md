# Handover — start here

This is the "first five minutes" file for an AI new to this repository. It
tells you what the project is, where the real rules live, how to verify a
change, and which mistakes have already bitten a previous AI session so you
don't repeat them. It does not duplicate the rules themselves — it points
you at the file that owns each one, so there's a single source of truth.

## Latest session handover (2026-08-18) — BOT-098F6D native chart cutover

**What just landed (commit `d0eea47`, already on `master-warrior`):**
`BacktestChartHostFactory` now actually selects the native C++ chart host
for the Backtest screen's OHLC mode, config-driven
(`backtest.chart.backend` = `python|native|auto`, `python` is still the
shipped default — native is opt-in only, nothing changed for existing
users). Full detail, including three real bugs found and fixed via actual
interactive use (not just automated tests) — a `refresh_chart()` crash on a
`None` result, a blank-white chart background before any data arrives, and
strategy/script indicator lines silently vanishing after a chart-mode
round-trip — is in
[`Tasks/in_progress/BOT-098F6D_backtest_native_opt_in_cutover.md`](../Tasks/in_progress/BOT-098F6D_backtest_native_opt_in_cutover.md).
Read that file's `## Result` section before touching this area again; don't
re-derive what it already explains.

**To manually see the native chart running** (`./scripts/run-ui.ps1`):
set `SAGITTARIUS_BACKTEST_CHART_BACKEND=native` as an environment variable
for that one shell session — do **not** add `backtest.chart.backend` to the
committed `src/config/user_config.json`. That was tried mid-session and it
broke two pre-existing sanity/integration tests that boot the real app via
`create_app()` and implicitly inherit whatever that file says (they assumed
the Python-only `.chart_card` attribute exists) — the env var override
exists specifically so local manual testing never has to touch a shared,
committed config default.

**Two pre-existing bugs, confirmed unrelated to the chart work above, were
found during the same manual testing session and are filed but not yet
fixed:**
[`BUG-009`](../Tasks/bug_report/BUG-009_backtest_cached_frame_preview_widget_shift.md)
(Python-only cached-frame drag-preview widget appears to reposition, then
snaps back — `chart_card/cached_frame_interaction.py`, not yet root-caused)
and
[`BUG-010`](../Tasks/bug_report/BUG-010_backtest_sync_never_satisfies_range_coverage.md)
(clicking "Đồng bộ dữ liệu ngay" repeatedly never clears the "missing
candles" banner — possible cutoff mismatch between the coverage query and
`_published_candle_cutoff()`, not yet root-caused). Both have a documented
next-steps list; follow this repo's own test-first bug rule
(`.agents/rules/code-rule.md`) when picking either up — reproduce and
confirm the hypothesis before touching code.

**Also planned but not started:**
[`BOT-098F6F`](../Tasks/backlog/BOT-098F6F_native_equity_and_both_subplot_support.md)
— native chart backend only covers OHLC candlestick mode today; Equity and
BOTH (dual-pane) modes always fall back to Python by design
(`NativeChartItem` has no line-series draw mode or second subplot region
yet). Has open design questions the user hasn't answered — don't start
implementing without reading and resolving those first.

**A note on how this session went, for calibration:** the user pushed back
hard, more than once, when test coverage that only checked "no crash, no Qt
warning" was reported as sufficient evidence — the actual bugs found were
silent visual/state defects that kind of check structurally cannot catch.
`scripts/native_backtest_desktop_e2e.py` now samples real composited pixels
via `widget.grab()` for exactly this reason. If you extend native-rendering
work, verify what the user actually *sees*, not just what the code claims
to have constructed.

## What this project is

**Sagittarius Elite Warrior** is a Binance trading bot: a Python desktop app
(PySide6 + QML/Qt Quick UI) built on **Clean Architecture**, itself built on
top of a separate shared framework, **Sagittarius Engine**. Two repos work
together:

- `Sagittarius-Engine/` — the **superproject**. Contains the shared
  `sagittarius_engine/` framework (DI container, `IThreadManager`,
  `ConfigManager`, the `pyside_mvc` extension with shared QML components
  like `StatefulButton.qml`). Its own `.agents/` playbook
  (`Sagittarius-Engine/.agents/PLAYBOOK.md` + `rules/`, `skills/`,
  `context/`) is generic — it doesn't know this app exists.
- `Sagittarius_Elite_Warrior/` — this **submodule**. The actual bot
  application: `src/domain/`, `src/application/`, `src/infrastructure/`,
  `src/presentation/ui/` (PySide6 screens, each a `<name>_presenter.py` /
  `<name>_view.py` / `<name>_view_model.py` MVP trio plus QML). This is
  where you'll do almost all real work.

## Installation & Dependencies

### Option 1: Install from GitHub Repository (Production / Shared)
```bash
pip install git+https://github.com/anhembedded/Sagittarius-Engine.git
```

### Option 2: Local Editable Installation (Development)
```bash
pip install -e Sagittarius-Engine
```

## Where the actual rules live (read these, don't guess)

- **`.agents/rules/code-rule.md`** (this folder) — the real, binding
  engineering rules for this submodule: No Hardcoding, SOLID, No Lazy Code
  (no `lambda` — write a named function instead), mandatory sanity tests
  for every new feature/screen, write-a-regression-test-before-fixing-a-bug,
  and the flat MVP-trio screen folder convention. Read it in full before
  writing any code — this summary is not a substitute.
- **`.agents/rules/install-rule.md`** (this folder) — installation guidelines and
  dependency setup for `sagittarius_engine` (GitHub URL install vs. local editable).
- **`.agents/rules/native-chart-rule.md`** — mandatory CMake build, Qt/PySide ABI,
  staging, and verification rules for `Sagittarius.NativeChart`. User commands
  live in `Docs/NATIVE_CHART_BUILD_AND_DEPLOY.md`.
- **`.agents/AGENTS.md`** (this folder) — short SOLID recap plus the
  mandatory commit signature: every AI-authored commit ends with
  `Co-Authored-By: Antigravity <noreply@google.com>`.
- **`.agents/context/`** (this folder) — workload-specific, non-binding
  context. Read the matching file when working in that area; it records
  current facts, task order, and known hazards without duplicating rules.
  For Backtest lifecycle/FSM/async work, read
  `.agents/context/BOT-095_backtest_lifecycle.md` before editing code.
- **`../.agents/PLAYBOOK.md`** (superproject root) — generic AI working
  process (understand → load context → apply rules → pick a skill →
  execute → validate). Its context/rule/skill routing tables reference an
  `.ai/` path that doesn't actually exist in this repo (the real directory
  is `.agents/`) — a known stale reference, not something to "fix" as a
  drive-by unless asked.
- **`Tasks/ROADMAP.md`** — the live status board: completed vs. backlog
  task counts, and a table of every `BOT-XXX`/`BUG-XXX` task. Check this
  before assuming a feature is missing or unimplemented.
- **`.jules/bolt.md`, `.jules/palette.md`, `.jules/sentinel.md`** —
  running journals (critical learnings only, not logs) for three daily
  automation agents: Bolt (performance), Palette (UX/accessibility),
  Sentinel (security). `.jules/*.prompt.md` are their actual system
  prompts. If you're doing performance/UX/security work, read the
  matching journal first — it already has real, codebase-specific lessons.

## How to verify a change (real commands, ground truth)

From inside `Sagittarius_Elite_Warrior/`:

```bash
ruff check src tests
ruff format --check src tests
```

Full test suite, run from the **superproject root** (`PYTHONPATH=..` is
load-bearing — tests import this app as the `Sagittarius_Elite_Warrior`
package):

```bash
PYTHONPATH=.. QT_QPA_PLATFORM=offscreen pytest Sagittarius_Elite_Warrior/tests \
  --ignore=Sagittarius_Elite_Warrior/tests/integration/presentation/ui \
  --cov=Sagittarius_Elite_Warrior/src --cov-report=term-missing --cov-fail-under=80 -v
```

This is exactly what `.github/workflows/ci.yml` runs, and what
`scripts/ci-local.ps1` wraps (`-SanityOnly` / `-UnitOnly` for fast
subsets during a dev loop, `-Full` for the gated version above,
`-IncludeFlakyUi` to deliberately include the excluded UI-integration
suite). `tests/integration/presentation/ui/` is skipped by default in
`ci-local.ps1` because it has a known intermittent native Qt/PySide6
crash (tracked as `BOT-038`) — do not "fix" that as a drive-by, it's an
open investigation, and note the actual GitHub Actions workflow does
**not** exclude it (a real, unresolved discrepancy).

## Test-writing gotchas already discovered here

These cost real debugging time in previous sessions — check them before
you hit the same wall:

- **`Repeater`-instantiated QML items are invisible to `findChild()`.**
  `findChild()` walks the QObject tree; `Repeater` delegates only exist in
  the *visual* tree. Use this repo's own `qml_item` / `find_qml_item`
  pytest fixture (`tests/conftest.py`) instead.
- **A QML item's local `y`/`x` can look correct while it's actually
  clipped or off-screen.** Local coordinates are relative to the
  *immediate* parent and stay "correct" even past a clipped boundary. Use
  `item.mapToItem(root, 0, 0)` to get the real absolute position before
  comparing against a widget's bounds.
- **A single `qapp.processEvents()` is not enough** for anything that
  depends on QtQuick Layouts' deferred `implicitHeight`/`implicitWidth`
  recompute — it passes in isolation but flakes once run alongside the
  rest of the suite. Use `qtbot.waitUntil(condition, timeout=...)`.
- **`QQuickItem.ensurePolished()` only forces the polish job on the exact
  item you call it on.** If the pending recompute actually lives on a
  child `ColumnLayout`/`RowLayout`, calling it on the parent silently
  reads a stale value — find the actual item with the pending layout
  (`objectName` + `findChild`) and call it there.
- **Never put `onClicked` on a `MouseArea` nested inside a `Button`.**
  Real mouse clicks still work, but `qml_item(root, name).clicked.emit()`
  from a Python test finds nothing — the handler moved off the `Button`
  itself. This exact regression has happened twice (`BOT-057`, `BOT-083`).
- **`QQuickWidget`'s default resize mode is `SizeRootObjectToView`** — the
  root QML item's `implicitWidth`/`implicitHeight` are ignored unless
  Python explicitly reads them back and calls
  `setFixedHeight()`/`setMinimumHeight()`. A hardcoded pixel constant on
  the Python side is a red flag; prefer binding to the QML's own computed
  `implicitHeight`.
- **The bundled Basic-style `ScrollBar.qml`** renders invisible
  (`opacity: 0.0`) until `state === "active"`. `policy: AsNeeded` alone
  produces a scrollbar nobody sees; use a ternary between `AlwaysOn` (when
  content actually overflows) and `AlwaysOff`.
- **Popup bounds need an overlay assertion, not merely a click assertion.**
  For a modal hosted through `OverlayHost`, assert `overlay_host.overlay_size`
  from Python. It reads QML's real `Overlay.overlay` dimensions, which catches
  a popup trapped inside a short `QQuickWidget`; `find_qml_item()` alone cannot
  inspect Popup content reliably.

## Naming collision to watch for

`src/presentation/ui/assets/palette.py` defines a `Palette` class (the
app's real theme-color tokens, exposed to QML as `Theme.*`). This is
unrelated to the "Palette" UX agent in `.jules/palette.prompt.md` — don't
confuse the two when either is mentioned.

## When you're unsure

Search the repo first — `Tasks/ROADMAP.md`, existing tests, existing
screens under `src/presentation/ui/screens/` — before asking the user or
inventing behavior. Only ask if the answer genuinely isn't findable.
