# SPEC-011 — Start the app, and choose developer mode

- **Status:** ✅ built and proven
- **Actor:** trader (developer mode: developer)
- **Origin:** ADR D13 and D14 (user decisions of 2026-09-13), built as `EPIC-025` PR 1.5a
  and PR 1.5b; reshaped by `EPIC-033C` (the workbench window, HLD §11.2), which dropped the
  Welcome screen: the app opens on the last mode, as Windows applications do, and developer mode
  is a page of Tools → Options.
- **Surfaces:** the workbench window (title bar, status bar, Help → About), Tools → Options →
  Developer, and the Developer mode (`EPIC-033P`), which only developer mode has.

## 1. Trigger

*"I have just opened the app. Show me which exchange it is pointed at, and let me get on with
it."*

## 2. Preconditions

1. The application starts — `python -m Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper`,
   or the packaged launcher.
2. `src/config/app_config.json` is readable; `user_config.json` is the one writable file
   (`load_app_config()` loads it that way).
3. Nothing else: the window exists before any credential, symbol or venue has been checked.

## 3. Main flow

1. The window opens on the mode the last session ended in; the first run opens on the Futures
   desk, the registry's default. The window title and the status bar name the venues this run
   talks to, in text.
2. Help → About names the application, its version, the Engine's version and the venues.
3. The actor works: a mode-bar click, Ctrl+1…, or View shows another mode.
4. Optionally, the actor opens Tools → Options → Developer and ticks **Developer mode**. Nothing
   is written until OK or Apply; Cancel puts the switch back.
5. On OK or Apply the app writes `dev.mode` to `user_config.json` and, because the written value
   now differs from the one this run started with, says the setting takes effect after a
   restart and offers **Restart now**.
6. On **Restart now** the app starts a fresh process and quits this one. With developer mode
   turned *off*, `--dev` and `--debug` are stripped from the new command line — otherwise the flag
   would win over the file that was just written.
7. The next run reads `dev.mode` once, at boot, and the Developer mode exists or does not exist
   for the whole of it: the last mode on the mode bar, the event log in its centre (each event
   the bus publishes, how many handlers heard it, and any handler that raised) and the modules'
   probes docked on its right (HLD §11.2.1).

## 4. What must be true afterwards

- The window names its venues in the title and the status bar; the actor does not have to open
  anything to learn whether this run can send a real order.
- The mode the actor last used comes back on the next launch, shown as a restore and not as a
  click: **launching opens no market stream and sends no live-stream command, whichever mode
  comes back** (`BUG-104`). A restored Market mode says its market data is not live; the Dev Board's opt-in
  auto-start waits too. Either goes live when the actor clicks its mode, the showing one
  included.
- Every mode is built at start (the user's decision, 2026-10-04); a screen goes live on the
  actor's open (`IShownAsMode`), never when it is built.
- After the switch is applied and the app restarted, `dev.mode` is `true` in `user_config.json`
  and the Developer mode is on the mode bar, showing the `trading` module's session probe.
- With developer mode off there is no Developer mode, no command of its mode, and nothing
  observing the event bus.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| `user_config.json` cannot be written (read-only file, no writable file loaded) | The switch returns to the saved position, no restart is offered, and the failure is logged with the value that was refused | The restart notice is a statement about the file on disk. Offering a restart after a failed write is a lie the actor would act on |
| The new process cannot be started on **Restart now** | This session keeps running, and the log says the start failed and that the setting applies at the next normal launch | An app that quits without starting its replacement leaves the actor with nothing. The setting is already written, so a manual relaunch loses nothing |
| The remembered mode no longer exists (a screen retired since) | The window opens on the default mode | A remembered value is a request, never a command (`IStateContributor`) |
| No screen claims the default route | The app refuses to open the window, naming the missing default | Guessing a mode would mean opening one nobody chose |
| Two screens claim it | Boot fails and names both | `ContributionRegistry`'s refusal, so a second default is a wiring mistake found at boot rather than a race for which mode shows |

## 6. What this use case does NOT promise

- **Opening the app is not a login.** It authenticates nothing and checks no credential. The day
  there is a real login, it comes before the window, not as a mode.
- **Developer mode does not change in place.** It is read once, at boot, because it decides
  whether a whole surface exists. Nothing re-reads it, and no module is loaded or unloaded at
  runtime.
- **Developer mode is not a permission.** It shows probes and chart diagnostics; it does not
  enable, disable or widen anything about live trading. Turning it on does not make the app
  able to trade, and turning it off does not make it safe.
- **The Dev Board screen itself is still always present**, until `EPIC-033P` stage 3 deletes it.
  A screen can be gated since `EPIC-033P` stage 2 (`ScreenContribution.gated_by`, which drops the
  screen and its mode's commands), and the Developer mode is; the Dev Board is not, because the
  Market mode does not yet offer all it does (`EPIC-033Q`, `EPIC-033S`).

  The history of that asymmetry, kept because the decision it records still holds for the
  Dev Board: until stage 2, `ContributionRegistry.contribute()` evaluated `surface_is_open()` for a
  contributed **panel**, while `contribute_screen()` evaluated no gate at all.

  That asymmetry is a promise, not an oversight. The screen still carries manual order entry and
  the strategy controls, and **nothing on the Trading surface carries them** — measured rather
  than assumed: `grep -rn "manual_order"` over the Trading screen's package was empty, while
  `dashboard_presenter.py` holds the manual-order action, its ownership tracker and the
  armed-symbol block reason. Gating the screen before they move would take a capability away from
  the actor, which ADR D12 forbids as an undeclared behaviour change. So the blocker is a **home
  on Trading for those two things** — a feature placement, and the actor's call — not a missing
  gate; it travels with the screens into `modules/trading/ui/` in Phase 2 + Phase 4
  (`Tasks/epics/EPIC-025_module_theo_bounded_context/DECISION_2026-09-16_the_duplication_criterion_waits.md`).
  `EPIC-025B`'s "done when" list carried the **opposite** sentence until 2026-09-16 and was
  corrected against this clause; `TRACKING.md` carries the per-pull-request record.

## 7. Ports and modules it exercises

`core`: `IConfigWriter` — the write side of configuration, whose first caller this is — and
`IShownAsMode`, how a mode hears it was shown and why. `shell`: the Developer options page and
`argv_for_restart()`. The Engine: `WorkbenchShell`, its `ActionRegistry` and its Options dialog.
No bounded context is involved, which is the point: this is about the application, not about
market data, trading or a strategy.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The window opens on the default mode as a restore, brings the last mode back as a restore, falls back to the default for a retired mode, and names the venue in the title and status bar | `tests/unit/presentation/ui/test_main_window_navigation.py` | unit |
| The switch writes and saves only on Apply, offers the restart only after the write, and puts itself back on a failed save | `tests/unit/shell/test_developer_options_page.py` | unit |
| What the next process is told, including the stripped `--dev` | `tests/unit/shell/test_developer_mode_restart.py` | unit |
| A failed start leaves this session running | `tests/unit/shell/test_developer_mode_restart.py` | unit |
| The Futures desk is the default route, and survives the round trip into `ScreenRegistry` | `tests/unit/shell/test_screen_wiring.py` | unit |
| Launching with any mode remembered opens no market stream and dispatches no `StartLiveStreamCommand`; a restored Dev Board does not auto-start, a clicked one does; the last mode and a closed panel survive a real restart | `tests/integration/presentation/ui/test_main_window_state.py` | integration |
| The version shown is the version the project declares | `tests/unit/architecture/test_app_version_matches_pyproject.py` | unit |
| A gated screen is dropped with its mode's commands when developer mode is off, and is a mode when it is on; the shell contributes the Developer mode | `tests/unit/shell/test_contribution_registry.py`, `tests/unit/shell/test_contribution_assembly.py` | unit |
| The Developer mode: the event log central, what the bus publishes and a raising handler reaching it, a burst it could not keep said in words, a contributed probe docked right, recording from the window's build until it shuts down | `tests/unit/shell/developer_mode/test_developer_mode.py`, `tests/unit/shell/developer_mode/test_bus_event_recorder.py` | unit |
| With developer mode on, the Developer mode builds in the real window and passes the conformance suite with no baseline row | `tests/sanity/test_composition_root.py`, `tests/integration/presentation/ui/test_workbench_conformance.py` | sanity, integration |
| Developer mode end to end | **the user runs it**: Tools → Options → Developer, tick Developer mode, OK, press Restart now, and confirm the app comes back with a Developer mode whose log fills as the app runs and whose right side shows the *Trading session* probe — then untick it, restart again, and confirm the Developer mode is gone | human |
