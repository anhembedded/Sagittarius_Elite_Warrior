# SDD §4 — Boot, and writing configuration

> Part of the SDD, split out of the single `README.md` this document used to be
> (2026-09-15, user decision). Every `###` heading below is **verbatim** from that
> file, so a reference written as *"SDD, 'Threading contract'"* still resolves.
> [`README.md`](README.md) is the index.

What `register()` may do versus `boot()`, the order the shell boots in, and
the two config paths that change what the next boot does — `IConfigWriter`
and the `dev.mode` toggle with its restart.

### `register()` versus `boot()` — what each may do

| | `register(context)` | `boot(context)` | `contribute(registry)` / `subscribe(bridge)` |
| :--- | :--- | :--- | :--- |
| DI | `singleton` / `bind` only | `resolve` allowed | `resolve` allowed; factories resolve later |
| I/O, threads, network | never | start hosted services and scheduler jobs | never |
| Qt | never | never | descriptors only; no widget module imported (lazy factories) |
| Guard | container spy fails on `resolve` | — | registry spy fails on factory call; `sys.modules` check |

### The shell's boot procedure (SDD-02, in prose)

1. Read configuration **once**, in one `ConfigManager` shared by the GUI and headless paths (today
   there are two: `main.py:108` and `app_bootstrapper.py:178`; unifying them is a declared
   behaviour change — headless `--dev` starts working). `dev.mode` is captured for the whole run;
   `--dev` on the command line wins.
2. Construct `QApplication` (the Engine's proven ordering: before `App.boot()`).
3. `app.use(module)` for each entry of `MODULES`, **in the list's own topological order** — the
   list is the source of truth; the Engine's `dependencies` sort is a check, not the mechanism.
4. `DoubleClaimCheck`: for every abstract type in `container.registrations()`, at most one module
   registered it; otherwise fail before `boot()`.
5. `app.boot()`.
6. `contribute()` then `subscribe()` for each module, in list order; then the shell registers its
   own surfaces and, during the strangler period, wraps each remaining `AbstractScreenModule` in a
   `ScreenContribution` whose factory calls `create_view()` / `create_presenter()` lazily
   (`LegacyScreenAdapter`, deleted in Phase 4).
7. Build `MainWindow` from `registry.screens()`; the default route is `welcome`.

### Writing configuration — `IConfigWriter`

`core/contracts/i_config_writer.py`: `set(key: str, value: object) -> None` and `save() -> None`.
The shell implements it as an adapter over the Engine's `ConfigManager` (today the settings
presenter downcasts with `isinstance(self.config, ConfigManager)` at `settings_presenter.py:274`;
that downcast disappears). The Welcome switch and every settings section write through this port.

### `dev.mode` and restart (SDD-05)

- Gate evaluated **once**, in the shell, before `app.use()`; the `dev_board` surface is declared but
  gated off when false, so its contributions are dropped under validation rule 3 and its `screen`
  is never registered. Backtest's chart FPS overlay also follows `dev.mode`
  (`backtest_view.py:204`), so a restart changes it too — declared.
- The Welcome switch writes `dev.mode` through `IConfigWriter` (the writable `user_config.json`),
  then shows "takes effect after restart" and a **Restart now** button that calls
  `QProcess.startDetached(sys.executable, [sys.argv[0], *argv_without_dev_flags])` and quits — the
  script path is kept, and `--dev` / `--debug` are stripped when the switch turns developer mode
  off, otherwise the flag would win again on the next run. No module is loaded or unloaded at runtime.

