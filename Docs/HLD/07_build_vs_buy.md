# §7 — Build or buy: what already exists for each thing we plan to build

- **Status:** survey completed 2026-09-12 at the user's request (*"thử điều tra xem những vấn đề
  mình định dev thì có cái nào có framework, thư viện hay bất cứ gì hỗ trợ không?"* — "check whether
  any of the things we intend to build already have a framework, a library or anything supporting
  them"). Facts below were verified on PyPI on that date; two tools were installed into the project
  venv, run against the real tree, and uninstalled again.
- **Decision (user, 2026-09-13):** *"keep the plan the same, not substitute with lib"*. Nothing in
  this section replaces a planned piece of work. The survey stays as **reference**: it records what
  exists, what was measured, and why each candidate was set aside, so that the next person does not
  repeat the search. The one exception the user did not object to is the small Engine addition in
  §7.8 (`ScheduledJob.cancel()`), which adds no dependency.
- **How to read the verdicts.** *Adopt* means "use the library instead of writing the thing".
  *Borrow the pattern* means "do not depend on it, but copy its shape, because it has been vetted by
  a large project". *No* means "does not fit, and here is why". A verdict of *no* is still useful:
  it tells the next person not to re-run the same search.

## 7.1 Summary table

| Work item (HLD / ADR) | Candidates | Verdict |
| :--- | :--- | :--- |
| Boundary guards with a shrink-only allowlist (D11, §6.1) | **tach** 0.35.0 (MIT, Rust, May 2026) · **import-linter** 2.15 (BSD, Sep 2026) · pytest-archon 0.0.7 · PyTestArch | **Not adopted (user decision 2026-09-13)** — D11 stays hand-written AST guards. tach's model is the closest match and is the fallback if the hand-written guards ever become a burden (§7.2) |
| The module contract (D2, §3.1) | Engine `IExtension` (existing) · **pluggy** 1.6.0 (MIT) · **lato** 0.13.0 (MIT) | **Keep the Engine**; borrow pluggy's spec/impl validation and lato's module-inclusion shape (§7.3) |
| Dependency injection (§3.1 double-claim check) | Engine `StdLibContainer` (existing) · svcs 26.2.0 · dependency-injector 4.49.1 | **Keep the Engine**; the double-claim check is a ten-line addition (§7.3) |
| Contribution points (§4.3) and the slot registry (`TASK-043`) | VS Code extension model · **napari / npe2** manifests · **Spyder** `SpyderPluginV2` + registries · Orange3, QGIS | **No library to import** — all are host-specific; **borrow** npe2's static descriptor and Spyder's `api.py` + container + registry shape (§7.4) |
| Regions / docking for the Engine runtime (`EPIC-001D`) | **PySide6-QtAds** 5.0.0.2 (LGPL v2.1, Aug 2026) | **Candidate for Phase 5**, decided in the Engine task; not needed before (§7.5) |
| Navigation service (`TASK-043`) | nothing in Qt or on PyPI beyond `QStackedWidget` | **Build** (small; the Engine's `PresenterManager` is the base) |
| Exchange gateway / Anticorruption Layer (`support/binance_gateway`) | python-binance (current) · **ccxt** 4.5.78 (MIT, Sep 2026) with ccxt.pro websockets | **Not now** (D12: no behaviour change); ccxt is the natural candidate for a second venue, and the gateway package is exactly the seam for it (§7.6) |
| "One execution port, two adapters" (backtest = live pipeline + `PaperExchange`) | **nautilus_trader** 1.231.0 (LGPL v3+, Rust core, Python ≥ 3.12) | **Not adoptable** (Python version, licence, it replaces our Engine); **read it as the reference architecture** before Phase 3 (§7.7) |
| Scheduler job cancellation (§5.1 gap) | APScheduler 3.11.3 (MIT) has `remove_job` / `pause` / `resume` | **Add `cancel()` to the Engine's `ScheduledJob`** instead — a small mechanism, no new dependency (§7.8) |
| Charting (`support/charting`, 27 files) | pyqtgraph (current) · **finplot** 1.9.7 (MIT, pyqtgraph-based) | **Keep chart_card** for Phase 4 (pure refactor); a later spike may compare (§7.9) |
| Indicators (`support/indicators`) | ta, pandas-ta, TA-Lib | **Keep** the pure implementations and the Pine-like DSL (D12) |

## 7.2 Boundary guards — tach, verified on the real tree

Two tools were installed and run from the package root (`/home/user`, because the app imports as
`Sagittarius_Elite_Warrior.src…`) against today's four layers, with the rule *domain ← application
← {infrastructure, presentation}*.

**tach** (`tach.toml`, 4 `[[modules]]` blocks, `depends_on` lists): **1.25 seconds**, 12 violations,
each reported as `file:line: Cannot use '<symbol>'`. **import-linter** (`.importlinter`, one `layers`
contract and one `forbidden` contract): analysed 697 files and 1,881 dependencies, found the same
12 plus one **indirect** chain (`app_bootstrapper → main → infrastructure`), which tach's direct-import
model does not report. import-linter needs the package importable from the working directory
(`PYTHONPATH`) and, with namespace packages (this tree has no `__init__.py` under `src/`), a
`root_packages` setting; tach needed neither.

**A finding in its own right.** Five of the twelve violations are `application → infrastructure`:
the handlers for `execute_order`, `enable_trading` (now `SessionReadiness`, `EPIC-034C`), `cancel_order`, `emergency_stop` and
`get_open_positions` construct `FuturesTradingClient` directly (documented as deliberate in
`EPIC-021` — "the only places allowed to construct it with `OrderSubmissionMode.LIVE`"). The
written rule (`architecture-rule.md` §3) forbids the import; the existing hand-written guard does
not catch it. The other seven are `presentation → infrastructure` (`binance_endpoints` in
`app_bootstrapper` and `settings_presenter`, `futures_order_payload_mapper` in two CLI commands,
the metadata cache in `backtest_presenter`). All twelve go into the Phase 0 allowlist as found;
Phases 1–4 remove them.

**Why tach was the strongest candidate** (recorded, not adopted — user decision 2026-09-13). Its model is the one this HLD designs:

| HLD concept | tach concept |
| :--- | :--- |
| a module's `dependencies` declaration (§3.1 rule 2) | `[[modules]] depends_on` |
| `contracts/` as the only importable surface (§3.3) | `[[interfaces]] expose` / `from` |
| the shrink-only allowlist (D11) | `tach sync` records violations as a baseline; `tach check` fails on new ones |
| layers inside a module (§3.2) | `layers` |
| the Engine's generalised `import_boundary` (`TASK-043` item 4) | already exists, in Rust, with pre-commit and CI hooks |

The user chose to keep D11 as designed: the guards are written by hand, in `ast`, inside the
repository's own test suite, so that the rule and its enforcement live in one place we control
and understand. The cost is a few hundred lines of guard code that tach would have provided; the
benefit is no dependency on a 0.x tool for the thing that keeps the architecture honest. What the
trial run still contributes: the twelve violations above are the **Phase 0 allowlist**, known
before a line of the guard is written. `TASK-043` item 4 (generalising the Engine's
`import_boundary`) therefore **stays**.

**Trade-offs, stated.** tach is a young project (0.x; first release 2024) with a company behind it
(Gauge); import-linter is older, pure Python, and its `grimp` graph finds indirect chains. If tach
ever stops being maintained, `tach.toml` translates mechanically into import-linter contracts; the
decision is reversible. pytest-archon and PyTestArch (ArchUnit-style rules inside pytest) were
considered and set aside: their value is expressing rules in test code, which is what we are
trying to stop hand-writing.

## 7.3 The module contract and DI — keep the Engine, borrow two ideas

**pluggy** (the plugin system under pytest, tox and Datasette) registers plugins explicitly with
`PluginManager.register()` and validates every `@hookimpl` against a `@hookspec` at registration
time — an unknown hook, or a wrong signature, fails immediately. That is exactly our guard (b) in a
different shape. We do not adopt pluggy, because its unit is a *hook* (a function many plugins
implement) while ours is a *port* (an ABC one module implements and others resolve); but the
"validate at registration, not at first call" rule is borrowed for `IContributionRegistry`: a
contribution whose descriptor does not match its kind's schema is rejected when the module
contributes, not when a surface renders.

**lato** (a Python micro-framework for modular monoliths: `Application`, `ApplicationModule`,
`include_submodule()`, `@module.handler` for commands and events, a `dependency_provider`
resolving by type hint, a transaction context) overlaps roughly seventy percent of what the Engine
already provides. Adopting it would mean replacing the Engine's kernel, which contradicts D10 (the
Engine is the user's reusable core). Its `include_submodule()` — a module that pulls in its own
sub-modules — is a good shape for a large module such as `backtesting` and is noted for Phase 3.

**svcs** and **dependency-injector** would replace `StdLibContainer`; neither prevents the silent
re-registration that §3.1 warns about (svcs deliberately allows overriding for tests). The
double-claim check stays a ten-line addition in `shell/`.

## 7.4 Contribution points — no library, two strong precedents

Every Python desktop application with plugins has built its own registry, because the *kinds* are
the host's business. Two are worth reading before round 2 answers ❓ O1:

- **napari / npe2.** A plugin ships a static manifest (`contributions: commands / widgets / readers /
  menus / sample_data …`) so the host knows what a plugin offers **without importing it**. That is
  the strongest form of the `EPIC-001D` principle "Python describes, QML renders": the descriptor is
  data, the factory is resolved lazily. Our frozen-dataclass descriptors (§4.3) follow this; the
  one thing to copy deliberately is that a descriptor must be constructible with no Qt import.
- **Spyder 5+.** A plugin (`SpyderPluginV2`) has an `api.py` (its public surface — our
  `contracts/`), a `PluginMainContainer` holding every widget it adds (our module's `ui/`), and
  registers actions, toolbars, menus and status-bar widgets into host registries. The
  `Plugins` enum plus `get_plugin()` is the same shape as `dependencies` plus `resolve()`.

## 7.5 Regions and docking — a real candidate for the Engine runtime

**PySide6-QtAds** wraps the Qt Advanced Docking System (LGPL v2.1; wheels for Windows, Linux and
macOS on Python ≥ 3.10; version 5.0.0.2 released 2026-08-04). It provides dock areas, floating
widgets and *perspectives* (saved and restored layouts). If the Engine's "regions" (`EPIC-001D`)
are to be user-rearrangeable, this is the library, and a `QQuickWidget` from `create_quick_widget()`
docks like any `QWidget`. Costs: one more native dependency; the LGPL obligation (dynamic linking,
which the wheel satisfies). This is a Phase 5 / `TASK-043` decision; Phases 0–4 keep `QStackedWidget`.

## 7.6 The exchange gateway — python-binance today, ccxt as the next-venue option

**ccxt** gives one API over more than a hundred exchanges, with Binance USDT-M futures supported and
websockets in ccxt.pro; it is MIT and released weekly. It is the obvious Anticorruption Layer for a
second venue. It is **not** adopted in this epic: D12 forbids behaviour change, the existing
adapters and their guard tests are written against python-binance, and ccxt's futures websocket
order stream has a history of gaps (a 2021 issue on `watch_orders()` for futures). The point of
`support/binance_gateway` is that when a second venue arrives, ccxt slots in behind the same three
ports without touching a module.

## 7.7 nautilus_trader — the reference architecture, not a dependency

NautilusTrader is an event-driven trading platform with a Rust core: one `DataEngine` and one
`ExecutionEngine`, per-venue `DataClient` / `ExecutionClient` adapters, and a `BacktestEngine` that
feeds the same engines — *"strategies deploy from research to production with no code changes"*. It
is exactly the "one execution port, two adapters" spike this HLD lists as optional. It cannot be
adopted here: it requires Python 3.12+ (this app runs 3.11), it is LGPL v3, it is headless by
design, and it would replace `strategy`, `trading` and `backtesting` wholesale — and the user's
Engine with them. Before Phase 3, read its *Adapters* and *Backtesting* concept pages and compare
with `PaperExchange`; the seam it suggests is `IOrderSubmission` implemented twice (live, paper).

## 7.8 Scheduler cancellation — a small Engine addition beats a dependency

APScheduler 3.11 has `remove_job`, `pause_job` and `resume_job`; the Engine's `Scheduler` has
neither (`max_runs` and `stop()` only). Wrapping APScheduler would add a second scheduler thread
and a second job model. Adding `ScheduledJob.cancel()` (a flag the scheduler loop honours) is a
few lines in the Engine, matches "Engine owns mechanism", and is filed as a note on `TASK-043`.

## 7.9 Charting — finplot is what chart_card re-implements

finplot (MIT) is a finance plotting layer on pyqtgraph — candlesticks, volume, indicators,
100k-candle performance, pan/zoom tuned for charts — which is what `components/chart_card`
(27 files, about 4,000 lines) does by hand. It is single-maintainer with its last release in May
2025. Phase 4 keeps `chart_card` (a pure refactor cannot swap a rendering stack); a later spike may
measure whether `support/charting` shrinks by adopting it. Not a decision for this epic.

## Sources

- tach — [github.com/tach-org/tach](https://github.com/tach-org/tach), [PyPI](https://pypi.org/project/tach) (0.35.0, MIT)
- import-linter — [contract types](https://import-linter.readthedocs.io/en/latest/contract_types.html), [PyPI](https://pypi.org/project/import-linter/) (2.15, BSD-2)
- pluggy — [github.com/pytest-dev/pluggy](https://github.com/pytest-dev/pluggy), [docs](https://pluggy.readthedocs.io/)
- lato — [github.com/pgorecki/lato](https://github.com/pgorecki/lato), [docs](https://lato.readthedocs.io/en/latest/)
- npe2 / napari — [Contributions reference](https://napari.org/dev/plugins/technical_references/contributions.html), [manifest proposal](https://github.com/napari/napari/issues/3115)
- Spyder — [Plugin development](https://docs.spyder-ide.org/current/workshops/plugin-development.html), [API elements](https://spyder-ide.github.io/spyder-api-docs/api_elements.html)
- PySide6-QtAds — [PyPI](https://pypi.org/project/PySide6-QtAds/)
- ccxt — [PyPI](https://pypi.org/project/ccxt/), [futures websocket issue #8067](https://github.com/ccxt/ccxt/issues/8067)
- nautilus_trader — [Adapters](https://nautilustrader.io/docs/latest/concepts/adapters/), [Backtesting](https://nautilustrader.io/docs/latest/concepts/backtesting/), [PyPI](https://pypi.org/project/nautilus-trader/)
- APScheduler — [user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- finplot — [github.com/highfestiva/finplot](https://github.com/highfestiva/finplot)
- pytest-archon — [github.com/jwbargsten/pytest-archon](https://github.com/jwbargsten/pytest-archon); PyTestArch — [PyPI](https://pypi.org/project/PyTestArch/)
