# Sanity Tier Audit & Remediation

> [!NOTE]
> **SA audit answering: "sanity isn't catching basic user cases."**
>
> Short answer: **correct — but not because the sanity tier is weak.** There
> are three separate causes, and only one of them is the sanity tier's fault.
> The other two matter more, and one of them is currently keeping **49% of the
> integration tier switched off in every default CI run**.
>
> Successor to [`qa_testing_strategy_report.md`](qa_testing_strategy_report.md)
> (BOT-015, measured at 477 tests). This one re-measures the tree as of
> 2026-08-25 (~1,700 tests) and goes specifically at the Sanity tier.
>
> Companion document: [`sanity_redesign_philosophy.md`](sanity_redesign_philosophy.md)
> — what the tier should have been, such that it could not have rotted this way.

---

## 1. Method and limits

**Sources** (each verified, nothing inferred):

- All 9 files under `tests/sanity/` — read in full, not sampled.
- `scripts/ci-local.ps1` — how the tier is actually invoked, not how the docs
  describe it.
- `.agents/rules/ci-rule.md` §6 (four-level test contract), `code-rule.md` §4.
- All 43 bug records in `Tasks/bug_report/` — the basis for the escape
  analysis in §5.
- `src/main.py`, `src/presentation/ui/app_bootstrapper.py`, `main_window.py` —
  comparing what sanity boots against what production boots.

**Limit, stated plainly:** this is **static analysis plus bug-record
correlation**, not a suite run. The authoring environment has neither `PySide6`
nor `sagittarius_engine`, and this project's CI is PowerShell/Windows-only
(`ci-local.ps1`). Every test count is derived from source; every behavioural
claim cites `file:line`. **The proposals in §6 have not been through CI** and
must be verified per `ci-rule.md` before merge.

---

## 2. Current state — the numbers

| Tier | Test functions | Files | Runs in default `-Full`? |
| :--- | ---: | ---: | :---: |
| `tests/unit/` | 1,339 | 153 | ✅ (parallel, 6 workers) |
| `tests/integration/` (excluding UI) | 37 | 15 | ✅ |
| `tests/integration/presentation/ui/` | **36** | 8 | ❌ **`--ignore` (BOT-038)** |
| `tests/sanity/` | 19 (→ **38 cases** after parametrize) | 9 | ✅ (sequential, background job) |

The figure of 38 matches what `BUG-041`/`BUG-042` recorded on 2026-08-24
(*"38 sanity"*), so this is the real state and not a miscount.

**What those 38 cases actually assert:**

| Assertion kind | Cases | Share |
| :--- | ---: | ---: |
| `container.resolve(X)` → `isinstance`, or registry content lookup | ~24 | **63%** |
| Class-level introspection (thread affinity, `unprotected_mutators`) | 5 | 13% |
| Constructing a real View + Presenter | 4 | 11% |
| Clean boot / health log / AST circular-import check | 5 | 13% |

**Cost:** the `booted_app` fixture is **function-scoped** in 5 of 6 files, so
the tier boots the entire real application roughly **24 times** to produce 38
assertions. That is why it has to run sequentially in a job of its own.

---

## 3. Three diagnoses

### 🔴 Diagnosis 1 — The sanity contract is written for an architecture the app no longer has

`code-rule.md` §4 requires sanity to *"boot the real app, construct real View +
Presenter, assert real DI resolves and **`quick_widget.errors() == []`**"*.

But **EPIC-006 migrated the entire UI off QML onto QtWidgets.** Confirmed:

- `grep -rn "QQuickWidget\|QmlHostView" src --include=*.py` → **comments only**;
  not one live usage remains.
- `app_bootstrapper.py:105` states it outright: *"EPIC-006F: no QML left in this
  app at all (the last consumer, the native chart, was deleted outright)"*.
- 22 `.qml` files still sit under `src/` in a *"kept on disk, unloaded"* state
  (`sidebar.py:141`, `data_management_view.py:238`, `settings_view.py:43`).

The knock-on effects:

1. **0 of 38 sanity cases call `errors()`** (`grep -rn "errors()" tests/sanity/`
   → empty). A mandatory clause of the rule was never enforced in the tier it
   governs — and now **cannot** be, because there is no `QQuickWidget` left to
   ask.
2. `tests/unit/.../test_preview_fixtures_exist.py::test_all_discovered_previews_build_cleanly`
   still asserts `widget.errors() == []` and walks `findChildren(QQuickWidget)`.
   After EPIC-006 both are **vacuous**: always empty, always green, guarding
   nothing.
3. `tests/conftest.py` has a session-autouse `_configure_app_qml` fixture
   configuring a whole QML stack that production **no longer initialises**
   (`app_bootstrapper.py:105`: *"which no longer needs calling here"*). The test
   harness is standing up an environment production does not have.
4. `test_qml_imports_match_engine_qmldir.py` and `test_qml_shared_foundation.py`
   guard 22 dead QML files. The first of those was added specifically to prevent
   a recurrence of `BUG-035`.

**This is the root of the feeling that sanity isn't doing its job:** the tier is
guarding something that no longer exists, and nobody has written the contract
for what does exist (QtWidgets).

### 🔴 Diagnosis 2 — The tier that proves user journeys is switched off, not missing

User-journey tests **do exist**: `tests/integration/presentation/ui/` — 36 test
functions covering navigation, a real "Sync Current" click, a full Dev Board
walkthrough, and Save on the Settings screen.

They are `--ignore`d from every default `-Full` run (`ci-local.ps1:359-361`)
because of `BOT-038`, an intermittent native Qt/PySide6 segfault.
`-IncludeFlakyUi` is opt-in, and per `ci-rule.md` §3 it is only expected *"when
a change touches that directory"*.

The result: **the integration tier that actually runs is 37 test functions
against 1,334 unit tests — 2.7%.** That is not a pyramid; it is a needle. A very
large body of unit tests, and almost nothing proving the pieces add up to a
usable application.

> **No sanity-tier proposal can compensate for this.** Sanity's own contract
> forbids clicks, dispatch and network (`ci-rule.md` §6, level 3). It is *not
> permitted* to catch user cases.

Worth noting: `BOT-038` §3 names its prime suspect as *"each iteration creates a
NEW `QQuickWidget`/`QQmlEngine`, no shared engine"*. **After EPIC-006 there are
no `QQuickWidget`s left in this app.** There is a real chance BOT-038 resolved
itself and nobody re-checked. See P2.0 in §6 — the highest benefit-to-cost
action in this report.

### 🟡 Diagnosis 3 — Within its own remit, the sanity tier has genuine holes too

Detailed in §4. In summary: it constructs **2 of 4 screens**, contains one
assertion-free test that can never fail, one docstring that misrepresents its
own assertion, no observation of Qt diagnostics at all, a boot fixture copied
six times that has already drifted, and a path where the whole UI portion
**skips silently**.

---

## 4. Ten specific findings

### F1 — `tests/integration/test_ui_sanity.py` is an empty test that always passes

```python
def test_sanity_ui_boot_and_navigation():
    print("Sanity Check GUI Setup...")
```

Eight lines, not one assertion, and a name promising "boot and navigation".
Pure fake-green: its only effect is to make the test count larger.

### F2 — A mandatory clause of `code-rule.md` §4 has never been enforced

`quick_widget.errors() == []`: **0 of 38** sanity cases. See Diagnosis 1.

### F3 — A docstring that claims more than the assertion delivers

`tests/sanity/test_health_boot_and_ui_sanity.py:106-112`:

```python
def test_real_mainwindow_construction_initializes_health_cleanly(...):
    """Assert constructing the full MainWindow renders cleanly with zero QML errors."""
    window = MainWindow(app)
    assert window is not None
```

`MainWindow.__init__` never returns `None`, so this test **cannot logically
fail** short of raising. It does not check "zero QML errors" as the docstring
claims. Anyone reading the test name and trusting it is being misled.

### F4 — Sanity constructs **2 of 4 screens**, and **zero modals**

`PresenterManager` is lazy-loading (`main_window.py:130`), and
`MainWindow.__init__` only calls `switch_screen("dashboard")`
(`main_window.py:119`).

| Screen | Constructed in sanity? |
| :--- | :---: |
| Dev Board (dashboard) | ✅ (`test_health_boot_and_ui_sanity.py`, and via MainWindow) |
| Backtest | ✅ (`test_backtest_screen_ui_sanity.py`) |
| **Database (data_management)** | ❌ **never** |
| **Settings** | ❌ **never** |

For the Database screen, sanity resolves 9 handlers from the container
(`test_database_screen_di_sanity.py`) and stops — **it never constructs the
View at all**. `BUG-019` (`GapInspectorModal` fails to build because `import
Sagittarius.Theme` does not exist — P1) landed exactly in that gap. The BUG-019
record itself recommended *"adding a sanity/preview check for every new
modal"*; that was never done.

### F5 — 63% of the tier proves "registered", not "callable"

`container.resolve(X)` returning an instance is not the same as that handler
working. Two defect classes walked straight through it:

- `BUG-020` — gap repair reported failure on success because it called
  `_run_check_status()`, **which does not exist**. The handler resolved cleanly.
- `BUG-026`/`BUG-027` — a test double missing 7 of 12 `IMarketDataRepository`
  methods. Caught by **mypy**, not by any test.

### F6 — Hand-written allowlists with no drift guard, though the correct pattern already exists in the same tier

`_BACKTEST_COMMANDS` (`test_backtest_screen_di_sanity.py:54`) and
`_DATABASE_COMMANDS` (`test_database_screen_di_sanity.py:54`) are typed by hand.
They catch something **removed** from `binance_bot_module.py`, and are
**completely blind** to a use case that is **newly added and never registered**
— which is the failure that actually occurs.

Contrast, in the same directory: `test_view_model_thread_affinity_sanity.py:62`
has `test_every_view_model_subclass_in_this_app_is_covered_by_this_list()`,
which scans real `__subclasses__()` and compares against the hand-written list.
**The right pattern already exists; it just was never copied to the two DI
files.** This is the cheapest fix in the report.

### F7 — No `tests/sanity/conftest.py`, so the fixture is copied 6 times and **has already drifted**

| File | Config loaded | WebSocket patched | Fixture scope |
| :--- | :--- | :---: | :--- |
| `test_bootstrapper_di_sanity.py` | app + user | ✅ | function |
| `test_backtest_screen_di_sanity.py` | app + user | ✅ | function |
| `test_backtest_screen_ui_sanity.py` | app + user | ✅ | function |
| `test_asset_preflight_sanity.py` | app + user | ✅ | (inline ×2) |
| `test_health_boot_and_ui_sanity.py` | app + user | ✅ | function |
| **`test_database_screen_di_sanity.py`** | app + user | ✅ | **module** |
| **`test_health_sanity.py`** | **app only** | ❌ **not patched** | (inline) |

`test_health_sanity.py` is the **only** sanity test that boots without patching
`AsyncClient`/`BinanceSocketManager`. Exactly one of the following is true, and
both are defects:

- it **genuinely touches the network** on boot, giving the tier a
  non-determinism nobody knows about; or
- the missing `user_config.json` makes it boot a **different** composition root
  from the other five, meaning it validates a configuration production never
  uses.

### F8 — A missing PySide6 **skips silently** and the tier still reports green

`tests/conftest.py:53`:

```python
except ImportError:
    pytest.skip("PySide6 not installed — skipping UI tests")
```

In an environment without Qt, the 4 UI-construction cases (11% of the tier)
vanish **without a sound**, and `-SanityOnly` still exits 0. For a tier whose
job is *proving composition health*, a broken environment must be a **failure**,
not a skip. (`BUG-043` — `run-ui.ps1` unable to import the local engine — is the
same class: environment broken, tests silent.)

### F9 — The log scan cannot see Qt messages

`Invoke-RunLogScan` (`ci-local.ps1:103`) greps `- (WARNING|ERROR|CRITICAL) -`,
which is Python's `logging` format. Qt emits diagnostics through a separate
channel:

- `qt.qml: Unable to assign [undefined] to double` → **BUG-028**
- `QBasicTimer::start: Timers cannot be started from another thread` → **BUG-031 (P1)**

Neither matches the pattern. And **no test file in the repository uses
`qInstallMessageHandler`** (repo-wide grep → 0 hits). Qt's entire diagnostic
channel is currently **unobserved at every tier**.

### F10 — No sanity coverage for shutdown

`app.stop()` appears only in fixture teardown, carrying no assertion. If it
hangs, the test **hangs** rather than failing — which is worse.

Three shutdown bugs, two of them P1, all reported by a human: `BUG-007`,
`BUG-023`, `BUG-041`. `MainWindow.shutdown()` / `closeEvent()`
(`main_window.py:121-127`) have never been invoked at the sanity tier.
`BUG-007`'s own *"Why sanity missed it"* section recorded this and concluded
that the status quo should stand.

---

## 5. Escape analysis — 43 bugs

All of `Tasks/bug_report/` classified by defect class, against the tier that
**should** have caught it:

| Defect class | Bugs | Count | Tier that should catch it | May sanity touch it? |
| :--- | :--- | ---: | :--- | :---: |
| Rendering / visual incorrectness | 002,003,004,005,006,009,012,014,021,032,034,037,038,039 | **14** | Desktop E2E / visual | ❌ forbidden |
| Threading / lifecycle / shutdown hangs | 001,007,011,013,023,031,033,041,042 | **9** | Sanity (extended) + Integration | 🟡 partly |
| Test-infrastructure flakiness | 015,016,029,030,036,040,043 | 7 | — (meta) | ❌ |
| Action wired but does nothing | 008,010,017,018,020 | **5** | Integration (user journey) | ❌ forbidden |
| **QML / module import breakage** | **019,028,035** | **3** | **Sanity** | ✅ **its own job** |
| Interface / port drift | 026,027 | 2 | mypy (did catch these) | ❌ |
| Performance / memory | 024,025 | 2 | Benchmark tier | ❌ |
| Domain logic incorrectness | 022 | 1 | Unit | ❌ |

**Two conclusions:**

1. **Only 3 of 43 (7%) fall within sanity's own remit — and sanity missed all
   three.** That is the tier's real share of the blame, and F4 + F9 explain it
   precisely: the Database screen is never constructed (→ BUG-019), Qt messages
   are never heard (→ BUG-028), and there is no "construct every screen" test
   (→ BUG-035).
2. **19 of 43 (44%) fall into two classes sanity is *forbidden* to touch**
   (visual incorrectness, and actions that do nothing). These are the "basic
   user cases" that are getting through. Their escape **is not sanity's fault**
   — it is the direct consequence of Diagnosis 2: the tier that proves them is
   switched off.

One further data point worth sitting with: several bug records explicitly note
CI was green and clean while the bug was live. `BUG-038`: *"1789 unit + 54
sanity, clean"* — found by a human looking at the screen. `BUG-039`: *"1800
passed / 54 sanity — nothing broke, i.e. **no test had ever asserted** that the
default was correct."* 93% coverage coexists with 43 filed bugs. **Coverage and
test count have saturated as signals on this project.**

---

## 6. Remediation

Ordered by benefit-to-cost, not by diagnosis number.

### P2.0 — 🚩 Do this before anything else: re-verify BOT-038 (cost: one run)

```powershell
.\scripts\ci-local.ps1 -Full -IncludeFlakyUi
```

Run it five times and record the results.

**Why:** `BOT-038` §3 concluded the suspect was *"each iteration creates a NEW
`QQuickWidget`/`QQmlEngine`, no shared engine"* — the same object-lifetime class
partially fixed in BOT-034. **EPIC-006 removed `QQuickWidget` from the app
entirely.** If BOT-038 has resolved itself, this one command unlocks **36
user-journey tests = 49% of the integration tier**, and addresses the largest
part of "why are basic user cases getting through".

This is the cheapest action in the report with the largest leverage.

- ✅ **If green 5/5:** drop the `--ignore` at `ci-local.ps1:359-361`, close
  BOT-038, update `ci-rule.md` §3. That closes 44% of the escapes.
- ❌ **If it still crashes:** BOT-038 becomes P1 and the blocking task for the
  whole quality roadmap. Preferred direction: move the `main_window`/`app_engine`
  fixtures (`tests/integration/presentation/ui/conftest.py`) to session scope
  with explicit teardown, instead of rebuilding the entire widget tree per test.

### P0 — Stop the fake-green (~0.5 day)

Do this before adding any new test — otherwise the drift and the fake-green get
copied forward.

| # | Finding | Fix |
| :--- | :--- | :--- |
| **P0.1** | F1 — empty test | Delete `tests/integration/test_ui_sanity.py`. What it promises is already done for real by `test_sanity_ui_e2e.py`. |
| **P0.2** | F7 — duplicated, drifted fixture | Add `tests/sanity/conftest.py` with **one** **session-scoped** `booted_app`, loading exactly what `app_bootstrapper.py:67-69` loads (including `writable=True`) and patching the WebSocket boundary consistently. Delete the 6 copies. Side benefit: **24 boots → 1**, roughly an order of magnitude off the tier's runtime. |
| **P0.3** | F8 — silent skip | Override `qapp` in `tests/sanity/conftest.py`: missing PySide6 → `pytest.fail`, not `skip`. For a composition-health tier, a broken environment is a valid result and must be red. |
| **P0.4** | F3 — misleading docstring | Fix `test_real_mainwindow_construction_initializes_health_cleanly`. After P1.2 it will have a real assertion to keep. |

### P1 — Rewrite the sanity contract for the QtWidgets architecture (~2–3 days)

| # | Finding | Fix |
| :--- | :--- | :--- |
| **P1.1** | Diagnosis 1 — obsolete rule | Amend `code-rule.md` §4: drop `quick_widget.errors() == []` (meaningless post-EPIC-006) and replace it with *"construct the real View + Presenter for **every** route registered in `MainWindow._setup_router()`, under `diagnostic_guard`, and shut down cleanly"*. **The rule must change before the code** — otherwise every new feature keeps shipping against a dead contract. |
| **P1.2** | F9 — Qt diagnostics unobserved | `diagnostic_guard` — an autouse fixture across the tier using `qInstallMessageHandler`, failing on `QtWarningMsg`/`QtCriticalMsg`/`QtFatalMsg`. Any allowlist must be narrow and declared line by line. **This is the true replacement for `errors()`** in a QtWidgets world, and it catches both `BUG-028` and `BUG-031` — neither of which `Invoke-RunLogScan` can structurally see. |
| **P1.3** | F4 — 2 of 4 screens | `test_every_registered_route_constructs.py`: lift the registry inside `MainWindow._setup_router()` into a module-level constant, then parametrize sanity **from that** rather than a hand-written list. 2/4 → **4/4**, and automatically covers screens added later. |
| **P1.4** | F6 — allowlists blind to additions | Replace `_BACKTEST_COMMANDS` / `_DATABASE_COMMANDS` with a scan: walk every `*Command`/`*Query` class under `src/application/use_cases/` and assert the container resolves it. Copy the drift-guard pattern already at `test_view_model_thread_affinity_sanity.py:62`. |
| **P1.5** | F10 — shutdown unguarded | Sanity shutdown test: boot → construct `MainWindow` → `window.shutdown()` + `app.stop()` **with a timeout**, asserting no live non-daemon threads remain. The `BUG-007`/`023`/`041` class (2× P1) currently has no tier watching it. |
| **P1.6** | Diagnosis 1 — dead assets | The 22 `.qml` files, `test_qml_imports_match_engine_qmldir.py`, `test_qml_shared_foundation.py`, the `_configure_app_qml` fixture in `tests/conftest.py`, and the now-vacuous `errors()`/`QQuickWidget` assertions in `test_preview_fixtures_exist.py`. Delete them, or move them to `Docs/legacy/`. **A test guarding dead code is not neutral — it dilutes the signal and manufactures false confidence.** |

### P2 — Close the user-journey gap (~1 week, after P2.0)

| # | Action |
| :--- | :--- |
| **P2.1** | If P2.0 comes back green: promote `tests/integration/presentation/ui/` to a required gate in `-Full` and retire `-IncludeFlakyUi`. |
| **P2.2** | Draw up the core user-journey catalogue from [`Docs/PROJECT_INTENT_AND_USER_STORIES.md`](../../Docs/PROJECT_INTENT_AND_USER_STORIES.md) and [`dev_board_user_end_test_cases.md`](dev_board_user_end_test_cases.md). One test per journey, run on **every** CI invocation. Prioritise by §5: the "action does nothing" class (5 bugs) first — cheapest, most deterministic, no real display needed. |
| **P2.3** | Amend `ci-rule.md` §6 to state outright that the Sanity tier is **structurally incapable** of proving user cases and that Integration owns that responsibility — so nobody reads "38 sanity passed" as evidence the app works. |

---

## 7. Metrics to track

Drop "test count" and "coverage %" as health indicators — §5 shows both have
saturated. Replace with:

| Metric | Now | Target |
| :--- | :---: | :---: |
| User-journey tests running in default `-Full` | **0** | ≥ 36 (P2.0) |
| Screens constructed by the sanity tier | **2 / 4** | 4 / 4 |
| Qt messages escaping CI | **not measurable** | 0 (measurable after P1.2) |
| Integration / Unit ratio (default run) | **2.7%** | ≥ 10% |
| Escape rate: bugs found by **users** / all new bugs, per month | not yet tracked | declining |

The last one is the only real metric. Everything above it is a proxy.

---

## 8. What not to do

- **Do not push user journeys into `tests/sanity/`.** The tier boots the real
  app, runs sequentially, and (before P0.2) boots 24 times. It is the most
  expensive place in the suite to add behaviour. Sanity must stay **fast and
  narrow**; user journeys belong to Integration.
- **Do not raise the coverage threshold.** 93% coverage coexists with 43 bugs
  and two P1s that *"no test had ever asserted"* (`BUG-039`). Raising the bar
  only produces more tests for the code that is easy to test.
- **Do not add new tests before P0.1 and P0.2 land.** Fake-green and fixture
  drift will be copied into every new file — which is exactly how the current
  six copies came about.
- **Do not delete `tests/sanity/` and fold it into integration.** The tier has
  real and unique value: `test_view_model_thread_affinity_sanity.py` blocks an
  entire defect class (BUG-001), and `test_circular_imports.py` catches
  something pytest structurally never reaches. The problem is **scope and
  contract**, not existence.

---

## 9. Action summary

1. **Run `.\scripts\ci-local.ps1 -Full -IncludeFlakyUi` ×5, now.** (P2.0) The
   result determines every priority behind it.
2. In parallel: P0.1–P0.4 (half a day, independent of the above).
3. Amend `code-rule.md` §4 (P1.1) **before** writing any new sanity test.
4. P1.2 (`diagnostic_guard`) and P1.3 (construct 4/4 screens) — the only two
   sanity-tier changes that genuinely close defect classes that have already
   escaped.

> The one-line answer to the original question: **sanity isn't catching user
> cases because it is forbidden to; the tier that should be catching them is
> `--ignore`d out of CI; and sanity's own contract was written for a QML
> architecture the app abandoned in EPIC-006.**

---

*Audit dated 2026-08-25, counted from source at commit `f27649e`. Static
analysis — the suite was not run (see §1, Limits). Every proposal requires
verification via `ci-local.ps1 -Full` before merge.*
