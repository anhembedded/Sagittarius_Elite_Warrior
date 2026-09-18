# SPEC-011 — Start the app, and choose developer mode

- **Status:** ✅ built and proven
- **Actor:** trader (developer mode: developer)
- **Origin:** ADR D13 and D14 (user decisions of 2026-09-13), built as `EPIC-025` PR 1.5a
  and PR 1.5b.
- **Surfaces:** the Welcome screen — the first screen the app opens, and the only one the shell
  itself owns.

## 1. Trigger

*"I have just opened the app. Tell me what it is, which exchange it is pointed at, and let me
get on with it."*

## 2. Preconditions

1. The application starts — `python -m Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper`,
   or the packaged launcher.
2. `src/config/app_config.json` is readable; `user_config.json` is the one writable file
   (`load_app_config()` loads it that way).
3. Nothing else: this is the screen that exists before any credential, symbol or venue has been
   checked.

## 3. Main flow

1. The app opens on **Welcome**, not on a trading screen and not on the developer testbed: it is
   the default route.
2. The screen names the application and its version, and says **which venue this run talks to** —
   both of them, because where prices come from and where an order would go are independent
   settings.
3. The actor presses **Start** (or Enter — it is the default button).
4. The app navigates to the Trading surface. Welcome stays in the sidebar; going back to it costs
   one click and starts nothing.
5. Optionally, the actor ticks **Developer mode**. The app writes `dev.mode` to
   `user_config.json` and says the setting takes effect after a restart, offering **Restart now**.
6. On **Restart now** the app starts a fresh process and quits this one. With developer mode
   turned *off*, `--dev` and `--debug` are stripped from the new command line — otherwise the flag
   would win over the file that was just written.
7. The next run reads `dev.mode` once, at boot, and the Dev Board's probes exist or do not exist
   for the whole of it.

## 4. What must be true afterwards

- The first thing the actor sees names the app and its venues; they do not have to open Settings
  to learn whether this run can send a real order.
- Pressing Start reaches Trading. Nothing about that navigation is remembered: the next launch
  opens on Welcome again, whatever route was last used (`BUG-104`).
- Booting constructs **only** the Welcome screen. Neither trading screen's Presenter — and so
  neither screen's feeds — is built until the actor navigates there.
- After the switch is ticked and the app restarted, `dev.mode` is `true` in `user_config.json`
  and the Dev Board shows the `trading` module's session probe.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| `user_config.json` cannot be written (read-only file, no writable file loaded) | The switch returns to its previous position, no restart is offered, and the failure is logged with the value that was refused | The restart notice is a statement about the file on disk. Offering a restart after a failed write is a lie the actor would act on, and would leave them wondering why the setting did not stick |
| The new process cannot be started on **Restart now** | This session keeps running, and the log says the start failed and that the setting applies at the next normal launch | An app that quits without starting its replacement leaves the actor with nothing. The setting is already written, so a manual relaunch loses nothing |
| No screen claims the default route | The app refuses to open the window, naming the missing default | Guessing a route would mean opening a screen nobody chose — including, before this use case existed, a developer testbed |
| Two screens claim it | Boot fails and names both | `ContributionRegistry`'s refusal, so a second default is a wiring mistake found at boot rather than a race for which screen shows |

## 6. What this use case does NOT promise

- **Start is not a login.** It authenticates nothing and checks no credential; it raises one
  intent that today means "go to Trading". The day there is a real login, the button stays and
  what the intent means changes.
- **Developer mode does not change in place.** It is read once, at boot, because it decides
  whether a whole surface exists. Nothing re-reads it, and no module is loaded or unloaded at
  runtime.
- **Developer mode is not a permission.** It shows probes and chart diagnostics; it does not
  enable, disable or widen anything about live trading. Turning it on does not make the app
  able to trade, and turning it off does not make it safe.
- **The Dev Board screen itself is still always present.** Only its contributed probes follow the
  switch, and the mechanism says why: `ContributionRegistry.contribute()` evaluates
  `surface_is_open()` for a contributed **panel**, while `contribute_screen()` evaluates no gate
  at all.

  That asymmetry is a promise, not an oversight. The screen still carries manual order entry and
  the strategy controls, and **nothing on the Trading surface carries them** — measured rather
  than assumed: `grep -rn "manual_order" src/modules/trading/ui/trading/` is empty, while
  `dashboard_presenter.py` holds the manual-order action, its ownership tracker and the
  armed-symbol block reason. Gating the screen before they move would take a capability away from
  the actor, which ADR D12 forbids as an undeclared behaviour change. So the blocker is a **home
  on Trading for those two things** — a feature placement, and the actor's call — not a missing
  gate; it travels with the screens into `modules/trading/ui/` in Phase 2 + Phase 4
  (`Tasks/epics/EPIC-025_module_theo_bounded_context/DECISION_2026-09-16_the_duplication_criterion_waits.md`).
  `EPIC-025B`'s "done when" list carried the **opposite** sentence until 2026-09-16 and was
  corrected against this clause; `TRACKING.md` carries the per-pull-request record.

## 7. Ports and modules it exercises

`core`: `IConfigWriter` — the write side of configuration, whose first caller this is, and
`IContributionTable` for the screen's own surface. `shell`: the Welcome screen, `StartRequested`,
and `argv_for_restart()`. No bounded context is involved at all, which is the point of a shell
surface: this screen is about the application, not about market data, trading or a strategy.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The screen names the app, its version and both venues; Start raises an intent and decides nothing | `tests/unit/shell/test_welcome.py` | unit |
| The switch writes and saves, offers the restart only after the write, and puts itself back on a failed save | `tests/unit/shell/test_welcome.py` | unit |
| What the next process is told, including the stripped `--dev` | `tests/unit/shell/test_welcome_restart.py` | unit |
| A failed start leaves this session running | `tests/unit/shell/test_welcome_restart.py` | unit |
| Welcome is the default route, and survives the round trip into `ScreenRegistry` | `tests/unit/shell/test_screen_wiring.py` | unit |
| Booting opens Welcome and constructs neither trading screen, whatever route was last stored | `tests/integration/presentation/ui/test_main_window_state.py` | integration |
| The version shown is the version the project declares | `tests/unit/architecture/test_app_version_matches_pyproject.py` | unit |
| Developer mode end to end | **the user runs it**: tick Developer mode, press Restart now, and confirm the app comes back with the Dev Board showing the *Trading session* probe — then untick it, restart again, and confirm the probe is gone | human |
